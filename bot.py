import logging
import asyncio
import os
import signal
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN, DATABASE_URL
from database import create_pool, create_messages_table
from handlers import start, handle_message
from utils import create_message_cache

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create a stop event
stop_event = asyncio.Event()

async def stop_signal_handler():
    """Handle stop signals"""
    stop_event.set()

async def main():
    try:
        # Initialize bot
        print("Starting bot...")
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Initialize database
        print("Connecting to database...")
        db_pool = await create_pool()
        await create_messages_table(db_pool)
        print("Database connected")

        # Set up bot data
        application.bot_data['db_pool'] = db_pool
        application.bot_data['message_cache'] = create_message_cache()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Check if we're running on Railway
        if os.getenv('RAILWAY_PUBLIC_DOMAIN'):
            # Production mode (Railway)
            railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN').rstrip('/')
            port = int(os.getenv('PORT', '8080'))
            webhook_url = f"{railway_domain}/webhook"
            
            print(f"Setting up webhook at {webhook_url}")
            await application.bot.delete_webhook(drop_pending_updates=True)
            await application.bot.set_webhook(
                url=webhook_url,
                allowed_updates=Update.ALL_TYPES
            )
            
            # Log webhook info
            webhook_info = await application.bot.get_webhook_info()
            print(f"Webhook info:")
            print(f"  URL: {webhook_info.url}")
            print(f"  Pending updates: {webhook_info.pending_update_count}")
            
            print(f"Starting webhook server on port {port}")
            
            # Initialize first
            await application.initialize()
            
            # Create webhook app
            from telegram.ext._utils.webhookhandler import WebhookServer
            webhook_app = WebhookServer(
                listen="0.0.0.0",
                port=port,
                url_path="webhook",
                webhook_url=webhook_url
            )
            
            # Start the application
            await application.start()
            
            # Run the webhook
            async with webhook_app:
                await webhook_app.serve_forever()
                
        else:
            # Local development mode
            print("Starting polling mode...")
            await application.bot.delete_webhook(drop_pending_updates=True)
            print("Bot is starting...")
            await application.initialize()
            await application.start()
            print("Bot is running...")
            
            # Start polling in the background
            asyncio.create_task(application.updater.start_polling(drop_pending_updates=True))
            
            print("Bot is ready to handle messages...")
            print("Press Ctrl+C to stop the bot")
            
            # Wait for stop signal
            try:
                await stop_event.wait()
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        print("\nShutting down...")
        try:
            if 'application' in locals() and application.running:
                await application.stop()
        except Exception as e:
            logger.error(f"Error stopping application: {e}")
        
        try:
            if 'db_pool' in locals():
                await db_pool.close()
        except Exception as e:
            logger.error(f"Error closing database: {e}")
        print("Cleanup complete")

def handle_interrupt():
    """Handle keyboard interrupt"""
    asyncio.get_event_loop().create_task(stop_signal_handler())

if __name__ == '__main__':
    try:
        # Set up signal handlers
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Handle signals
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(shutdown(loop, signal=s))
            )
            
        # Run the bot
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        loop.close()

async def shutdown(loop, signal=None):
    """Cleanup tasks tied to the service's shutdown."""
    if signal:
        logger.info(f"Received exit signal {signal.name}")
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()
