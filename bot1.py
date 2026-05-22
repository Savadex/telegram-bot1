import os
import requests
from datetime import timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

TOKEN = os.environ["BOT_TOKEN"]
SIGHTENGINE_USER = os.environ["SIGHTENGINE_USER"]
SIGHTENGINE_SECRET = os.environ["SIGHTENGINE_SECRET"]
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")

WARN_LIMIT = 3
user_warns = {}


async def send_log(context, text):
    if LOG_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=LOG_CHAT_ID, text=text)
        except Exception as e:
            print("Log gönderilemedi:", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("botumuz aktiftir.")


async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, reason):
    user = update.effective_user
    chat = update.effective_chat

    if not user or user.is_bot:
        return

    key = (chat.id, user.id)
    user_warns[key] = user_warns.get(key, 0) + 1
    warns = user_warns[key]

    await context.bot.send_message(
        chat_id=chat.id,
        text=f"⚠️ {user.first_name} uyarı aldı.\nSebep: {reason}\nUyarı: {warns}/{WARN_LIMIT}"
    )

    await send_log(
        context,
        f"🧾 LOG\nKullanıcı: {user.first_name}\nID: {user.id}\nGrup: {chat.title}\nSebep: {reason}\nUyarı: {warns}/{WARN_LIMIT}"
    )

    if warns >= WARN_LIMIT:
        try:
            until_date = update.message.date + timedelta(minutes=5)

            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )

            user_warns[key] = 0
            await context.bot.send_message(chat_id=chat.id, text=f"🔇 {user.first_name} 5 dakika susturuldu.")
            await send_log(context, f"🔇 {user.first_name} 5 dakika susturuldu.")

        except Exception as e:
            await context.bot.send_message(chat_id=chat.id, text=f"Yetkim yok: {e}")


async def sightengine_check(file_path):
    params = {
        "models": "nudity-2.1",
        "api_user": SIGHTENGINE_USER,
        "api_secret": SIGHTENGINE_SECRET
    }

    with open(file_path, "rb") as f:
        files = {"media": f}
        r = requests.post(
            "https://api.sightengine.com/1.0/check.json",
            files=files,
            data=params,
            timeout=30
        )

    data = r.json()

    nudity = data.get("nudity", {})
    sexual = nudity.get("sexual_activity", 0)
    sexual_display = nudity.get("sexual_display", 0)
    erotica = nudity.get("erotica", 0)
    very_suggestive = nudity.get("very_suggestive", 0)

    return (
        sexual > 0.45 or
        sexual_display > 0.45 or
        erotica > 0.55 or
        very_suggestive > 0.65
    )


async def check_file(update, context, file_id, reason):
    msg = update.message
    file_path = f"temp_{msg.message_id}"

    try:
        tg_file = await context.bot.get_file(file_id)
        await tg_file.download_to_drive(file_path)

        is_nsfw = await sightengine_check(file_path)

        if os.path.exists(file_path):
            os.remove(file_path)

        if is_nsfw:
            await msg.delete()
            await warn_user(update, context, reason)
            return True

    except Exception as e:
        print("Kontrol hatası:", e)
        await send_log(context, f"❌ Kontrol hatası: {e}")

        if os.path.exists(file_path):
            os.remove(file_path)

    return False


async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    msg = update.message

    # Fotoğraf kontrolü
    if msg.photo:
        await check_file(update, context, msg.photo[-1].file_id, "NSFW fotoğraf")
        return

    # Resim dosyası kontrolü
    if msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
        await check_file(update, context, msg.document.file_id, "NSFW görsel dosya")
        return

    # Sticker kontrolü: normal sticker silinmez, sadece NSFW algılanırsa silinir
    if msg.sticker and msg.sticker.thumbnail:
        await check_file(update, context, msg.sticker.thumbnail.file_id, "NSFW sticker")
        return

    # GIF kontrolü: tam GIF dosyası kontrol edilir
    if msg.animation:
        await check_file(update, context, msg.animation.file_id, "NSFW GIF")
        return

    # Video kontrolü: tam video dosyası kontrol edilir
    if msg.video:
        await check_file(update, context, msg.video.file_id, "NSFW video")
        return


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Banlamak için bir mesaja cevap ver.")
        return

    user = update.message.reply_to_message.from_user

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"⛔ {user.first_name} banlandı.")
    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Susturmak için bir mesaja cevap ver.")
        return

    user = update.message.reply_to_message.from_user
    until_date = update.message.date + timedelta(minutes=5)

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )

        await update.message.reply_text(f"🔇 {user.first_name} 5 dakika susturuldu.")
        await send_log(context, f"🔇 {user.first_name} manuel olarak 5 dakika susturuldu.")

    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")


async def warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Uyarı görmek için bir mesaja cevap ver.")
        return

    user = update.message.reply_to_message.from_user
    key = (update.effective_chat.id, user.id)
    count = user_warns.get(key, 0)

    await update.message.reply_text(f"{user.first_name} uyarı sayısı: {count}/{WARN_LIMIT}")


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("warns", warns))

app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, check_message))

print("NSFW GIF/Video algılamalı bot çalışıyor...")
app.run_polling()
