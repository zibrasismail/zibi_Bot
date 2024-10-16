import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
AI_BASE_URL = "https://models.inference.ai.azure.com"
SENTRY_DSN = os.getenv('SENTRY_DSN')
