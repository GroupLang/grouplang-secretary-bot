# Hello, provider testing
import os

class Config:
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    MARKETROUTER_API_KEY = os.environ.get('MARKETROUTER_API_KEY')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
