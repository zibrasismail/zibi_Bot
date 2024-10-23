import logging
import asyncio
import os
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
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

# Global application instance
application = None

async def webhook_handler(request):
    """Handle incoming webhook requests"""
    try:
        update_data = await request.json()
        update = Update.de_json(update_data, application.bot)
        await application.process_update(update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return web.Response(status=500)

async def setup_webhook(app, port):
    """Set up the webhook"""
    railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN').rstrip('/')
    webhook_path = '/webhook'
    webhook_url = f"{railway_domain}{webhook_path}"
    
    print(f"Setting up webhook at {webhook_url}")
    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.bot.set_webhook(url=webhook_url)
    
    # Log webhook info
    webhook_info = await application.bot.get_webhook_info()
    print(f"Webhook info:")
    print(f"  URL: {webhook_info.url}")
    print(f"  Pending updates: {webhook_info.pending_update_count}")
    
    # Add route
    app.router.add_post(webhook_path, webhook_handler)
    
    return app

async def init_bot():
    """Initialize the bot and database"""
    global application
    
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

    # Initialize application
    await application.initialize()
    await application.start()
    
    return application

async def run_webhook():
    """Run the bot in webhook mode"""
    try:
        # Initialize the bot
        await init_bot()
        
        # Set up webhook server
        port = int(os.getenv('PORT', '8080'))
        app = web.Application()
        app = await setup_webhook(app, port)
        
        # Configure cleanup
        async def cleanup(app):
            if application:
                await application.stop()
                if 'db_pool' in application.bot_data:
                    await application.bot_data['db_pool'].close()
        
        app.on_cleanup.append(cleanup)
        
        return app
        
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        raise

async def run_polling():
    """Run the bot in polling mode"""
    try:
        # Initialize the bot
        await init_bot()
        
        print("Starting polling mode...")
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.updater.start_polling()
        print("Bot is running...")
        
        # Keep the bot running
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Polling error: {e}", exc_info=True)
        raise
    finally:
        if application:
            await application.stop()
            if 'db_pool' in application.bot_data:
                await application.bot_data['db_pool'].close()

if __name__ == "__main__":
    try:
        if os.getenv('RAILWAY_PUBLIC_DOMAIN'):
            # Production mode
            port = int(os.getenv('PORT', '8080'))
            web.run_app(run_webhook(), host='0.0.0.0', port=port)
        else:
            # Local development mode
            asyncio.run(run_polling())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
