import logging
import asyncio
from telegram import Update
from telegram.constants import ChatAction  # Changed this line
from telegram.ext import ContextTypes
from database import insert_user_message, insert_ai_response
from ai_client import get_ai_response
from utils import get_cache_key, update_cache, get_cached_response

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Start command received: {update}")
    try:
        message = 'Hello! I am your AI assistant. How can I help you today?'
        sent_message = await update.message.reply_text(message)
        logger.info(f"Sent start message to user {update.effective_user.id}: {sent_message}")
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)

async def send_typing_action(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        while True:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            logger.debug(f"Sent typing action to chat {chat_id}")
            await asyncio.sleep(3)  # Reduced to 3 seconds for more frequent updates
    except asyncio.CancelledError:
        logger.debug(f"Typing action cancelled for chat {chat_id}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Message received: {update}")
    
    if update.message is None:
        logger.warning("Update has no message")
        return

    user_message = update.message.text
    chat_id = update.effective_chat.id
    
    try:
        # Start typing indicator
        typing_task = asyncio.create_task(send_typing_action(context, chat_id))
        logger.debug("Started typing indicator task")

        # Check cache first
        cache_key = get_cache_key(chat_id, user_message)
        cached_response = get_cached_response(cache_key)
        if cached_response:
            logger.info("Found response in cache")
            typing_task.cancel()
            await update.message.reply_text(cached_response)
            return

        logger.info("Processing message")
        db_pool = context.bot_data['db_pool']
        await insert_user_message(db_pool, chat_id, user_message)
        
        ai_response = await get_ai_response(user_message)
        logger.info(f"AI response received: {ai_response[:50]}...")
        
        await insert_ai_response(db_pool, chat_id, ai_response)
        update_cache(context.bot_data, cache_key, ai_response)

        # Stop typing indicator
        typing_task.cancel()
        logger.debug("Cancelled typing indicator task")

        await update.message.reply_text(ai_response)
        logger.info("AI response sent to user")
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("I'm sorry, but I encountered an error while processing your message. Please try again later.")
    finally:
        # Ensure typing indicator is stopped even if an error occurs
        if 'typing_task' in locals():
            typing_task.cancel()
            logger.debug("Ensured typing indicator task is cancelled")
