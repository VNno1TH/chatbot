"""
telegram_bot.py — Telegram bot integration using python-telegram-bot
Runs alongside Flask server using the same RAG pipeline.
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.config import TELEGRAM_BOT_TOKEN, HAUI_DEBUG
from src.rag.pipeline import handle_query

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Xin chào! 👋 Em là Trợ lý Tuyển sinh HaUI.\n\n"
        "Em có thể giúp anh/chị:\n"
        "📊 Tra cứu điểm chuẩn các ngành\n"
        "🧮 Tính điểm xét tuyển\n"
        "📋 Tìm hiểu ngành học, tổ hợp\n"
        "📝 Hướng dẫn thủ tục đăng ký, nhập học\n"
        "💰 Thông tin học phí, học bổng, KTX\n\n"
        "Hãy gửi câu hỏi cho em nhé!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Hướng dẫn sử dụng:\n\n"
        "Gửi câu hỏi bằng tiếng Việt, ví dụ:\n"
        '• "Điểm chuẩn CNTT 2025"\n'
        '• "Tính điểm: Toán 8, Lý 7.5, Anh 7.25, KV2-NT"\n'
        '• "Gợi ý ngành với 24 điểm tổ hợp A01"\n'
        '• "Ký túc xá giá bao nhiêu"\n'
        '• "Lịch tuyển sinh 2026"\n\n'
        "☎ Hotline: 024.3765.5121 / 0834.560.255\n"
        "🌐 tuyensinh.haui.edu.vn"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    if HAUI_DEBUG:
        logger.info(f"[TELEGRAM] User: {user_text}")

    # Show typing indicator
    await update.message.chat.send_action('typing')

    try:
        result = handle_query(user_text)
        answer = result.get('answer', 'Xin lỗi, em không thể xử lý câu hỏi này.')

        # Telegram has 4096 char limit per message
        if len(answer) > 4000:
            parts = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='Markdown')
        else:
            try:
                await update.message.reply_text(answer, parse_mode='Markdown')
            except Exception:
                await update.message.reply_text(answer)

    except Exception as e:
        logger.error(f"[TELEGRAM ERROR] {e}")
        await update.message.reply_text(
            "Xin lỗi, em gặp lỗi khi xử lý câu hỏi. Anh/chị thử lại sau nhé!"
        )


def run_telegram_bot():
    """Start the Telegram bot (blocking)."""
    if not TELEGRAM_BOT_TOKEN:
        print("[TELEGRAM] No bot token configured. Skipping Telegram bot.")
        return

    print(f"[TELEGRAM] Starting bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)


def start_telegram_bot_async():
    """Start Telegram bot in a separate thread."""
    if not TELEGRAM_BOT_TOKEN:
        print("[TELEGRAM] No bot token. Skipping.")
        return

    import threading

    def _run():
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            run_telegram_bot()
        except Exception as e:
            print(f"[TELEGRAM ERROR] {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print("[TELEGRAM] Bot started in background thread")
