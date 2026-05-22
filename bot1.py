import os
from telegram.ext import ApplicationBuilder, CommandHandler

TOKEN = os.environ["BOT_TOKEN"]

async def start(update, context):
    await update.message.reply_text("Bot aktif ✅")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

print("Bot başladı...")
app.run_polling()
