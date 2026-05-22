import os
import requests
from datetime import timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

TOKEN = os.environ["BOT_TOKEN"]
SIGHTENGINE_USER = os.environ["409272525"]
SIGHTENGINE_SECRET = os.environ["D9UK8JyVBn9HGuD9bcW3mUVVrkMmMqoC"]
LOG_CHAT_ID = os.getenv("-1003494221100")

NSFW_WORDS = [
    "porn", "porno", "nsfw", "sex", "seks", "nude", "çıplak",
    "onlyfans", "18+", "sikiş", "am", "göt", "yarrak"
]

WARN_LIMIT = 3
user_warns = {}


async def send_log(context, text):
    if LOG_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=LOG_CHAT_ID, text=text)
        except Exception as e:
            print("Log gönderilemedi:", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("NSFW koruma botu aktif ✅")


async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, reason="Uygunsuz içerik"):
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
        f"🧾 LOG\n"
        f"Kullanıcı: {user.first_name}\n"
        f"ID: {user.id}\n"
        f"Grup: {chat.title}\n"
        f"Sebep: {reason}\n"
        f"Uyarı: {warns}/{WARN_LIMIT}"
    )

    if warns >= WARN_LIMIT:
        try:
            until_date = update.message.date + timedelta(minutes=30)

            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )

            user_warns[key] = 0

            await context.bot.send_message(
                chat_id=chat.id,
                text=f"🔇 {user.first_name} 30 dakika susturuldu."
            )

            await send_log(context, f"🔇 {user.first_name} 30 dakika susturuldu.")

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
            timeout=20
        )

    data = r.json()
    nudity = data.get("nudity", {})

    sexual = nudity.get("sexual_activity", 0)
    sexual_display = nudity.get("sexual_display", 0)
    erotica = nudity.get("erotica", 0)

    return sexual > 0.55 or sexual_display > 0.55 or erotica > 0.65


async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    msg = update.message
    text = ""

    if msg.text:
        text += msg.text.lower()

    if msg.caption:
        text += " " + msg.caption.lower()

    for word in NSFW_WORDS:
        if word in text:
            await msg.delete()
            await warn_user(update, context, "NSFW kelime")
            return

    file_id = None

    if msg.photo:
        file_id = msg.photo[-1].file_id

    elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
        file_id = msg.document.file_id

    if file_id:
        try:
            tg_file = await context.bot.get_file(file_id)
            file_path = f"temp_{msg.message_id}.jpg"

            await tg_file.download_to_drive(file_path)

            is_nsfw = await sightengine_check(file_path)

            if os.path.exists(file_path):
                os.remove(file_path)

            if is_nsfw:
                await msg.delete()
                await warn_user(update, context, "NSFW görsel")
                return

        except Exception as e:
            print("Sightengine hata:", e)
            await send_log(context, f"❌ Sightengine hata: {e}")

    if msg.video or msg.animation or msg.sticker:
        try:
            await msg.delete()
            await warn_user(update, context, "Video/GIF/Sticker engellendi")
        except Exception as e:
            print(e)


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Banlamak için bir mesaja cevap ver.")
        return

    user = update.message.reply_to_message.from_user

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"⛔ {user.first_name} banlandı.")
        await send_log(context, f"⛔ {user.first_name} banlandı.")
    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Susturmak için bir mesaja cevap ver.")
        return

    user = update.message.reply_to_message.from_user
    until_date = update.message.date + timedelta(minutes=30)

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )

        await update.message.reply_text(f"🔇 {user.first_name} 30 dakika susturuldu.")
        await send_log(context, f"🔇 {user.first_name} manuel olarak susturuldu.")

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

print("merhaba nsfw botumuz çalısıyor")
app.run_polling()
