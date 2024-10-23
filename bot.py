import logging
import asyncio
import os
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
    try:
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
        application.add_error_handler(error_handler)
        print("Handlers added successfully")

        # Initialize the application
        await application.initialize()

        # Check if we're running on Railway
        railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
        port = int(os.getenv('PORT', '8080'))

        if railway_domain:
            # Production mode (Railway)
            print(f"Running in production mode")
            print(f"Railway domain: {railway_domain}")
            print(f"Port: {port}")
            
            # Delete any existing webhook first
            print("Deleting existing webhook...")
            await application.bot.delete_webhook(drop_pending_updates=True)
            
            # Set the new webhook
            webhook_url = f"{railway_domain}/webhook"
            print(f"Setting up webhook: {webhook_url}")
            
            await application.bot.set_webhook(
                url=webhook_url,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            # Verify webhook
            webhook_info = await application.bot.get_webhook_info()
            print(f"Webhook info: {webhook_info.url}")
            
            # Start the webhook server
            print(f"Starting webhook server on port {port}")
            await application.start()
            await application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path="webhook",  # Add this line
                webhook_url=webhook_url
            )
        else:
            # Local development mode
            print("Running in local mode (polling)")
            await application.bot.delete_webhook(drop_pending_updates=True)
            await application.start()
            await application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        if 'application' in locals():
            await application.stop()
            await application.shutdown()
        if 'db_pool' in locals():
            await db_pool.close()

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
