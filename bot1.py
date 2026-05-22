import os
from telegram.ext import ApplicationBuilder, CommandHandler

TOKEN = os.environ["8827021819:AAFImmcgaITO4cDayaSjeqMLP6RO1AQk5g0"]

async def start(update, context):
    await update.message.reply_text("Bot aktif ✅")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

print("Bot başladı...")
app.run_polling()