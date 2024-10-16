import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN, DATABASE_URL
from database import create_pool, create_messages_table
from handlers import start, handle_message
from utils import create_message_cache
# import sentry_sdk
# from sentry_sdk.integrations.asyncio import AsyncioIntegration

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,  # Change to DEBUG for more detailed logs
)
logger = logging.getLogger(__name__)

# Add a file handler
file_handler = logging.FileHandler('bot.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Initialize Sentry
# sentry_sdk.init(
#     dsn=SENTRY_DSN,
#     integrations=[AsyncioIntegration()],
#     traces_sample_rate=1.0
# )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    # sentry_sdk.capture_exception(context.error)

async def log_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug(f"Received update: {update}")

async def main():
    print("Starting the bot...")
    logger.info("Bot is initializing...")

    # Initialize database
    print("Connecting to database...")
    db_pool = await create_pool()
    await create_messages_table(db_pool)
    print("Database connected and table created.")

    # Initialize application
    print("Initializing Telegram bot application...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.bot_data['db_pool'] = db_pool
    application.bot_data['message_cache'] = create_message_cache()

    # Add handlers
    application.add_handler(MessageHandler(filters.ALL, log_update), group=-1)  # Log all updates
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Handlers added successfully")

    # Add error handler
    application.add_error_handler(error_handler)
    print("Error handler added")

    print("Removing webhook...")
    await application.bot.delete_webhook()
    print("Webhook removed")

    print("Starting polling...")
    await application.initialize()
    await application.start()
    print("Polling...")

    # Custom polling method
    offset = 0
    while True:
        try:
            updates = await application.bot.get_updates(offset=offset, timeout=30)
            for update in updates:
                offset = update.update_id + 1
                await application.process_update(update)
        except Exception as e:
            logger.error(f"Error in polling: {e}", exc_info=True)
        await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
        logger.info("Bot stopped by user")
    except Exception as e:
        print(f"Unhandled exception: {e}")
        logger.error(f"Unhandled exception: {e}", exc_info=True)
    finally:
        print("Bot shutdown complete")
        logger.info("Bot shutdown complete")
