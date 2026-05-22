import os
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from datetime import timedelta

TOKEN = os.environ["BOT_TOKEN"]
LOG_CHAT_ID = -1003494221100

NSFW_WORDS = [
    "porn", "porno", "nsfw", "sex", "seks", "nude", "çıplak",
    "onlyfans", "18+", "sikiş", "am", "göt", "yarrak"
]

WARN_LIMIT = 3
user_warns = {}

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
            await context.bot.send_message(chat_id=chat.id, text=f"🔇 {user.first_name} 30 dakika susturuldu.")
        except Exception as e:
            await context.bot.send_message(chat_id=chat.id, text=f"Yetkim yok: {e}")

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
            try:
                await msg.delete()
                await warn_user(update, context, "NSFW kelime")
            except Exception as e:
                print(e)
            return

    is_bad_media = False

    if msg.photo or msg.video or msg.animation or msg.sticker:
        is_bad_media = True

    if msg.document:
        mime = msg.document.mime_type or ""
        file_name = msg.document.file_name or ""

        if mime in ["image/gif", "video/mp4"]:
            is_bad_media = True

        if file_name.lower().endswith((".gif", ".mp4", ".webm")):
            is_bad_media = True

    if is_bad_media:
        try:
            await msg.delete()
            await warn_user(update, context, "Medya/GIF içeriği engellendi")
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

print("NSFW bot çalışıyor...")
app.run_polling()
