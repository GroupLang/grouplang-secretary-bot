# Hello, provider testing
import requests
import os
import json
import logging
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
BASE_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}'

def send_message(chat_id, text, reply_markup=None, reply_to_message_id=None):
    try:
        url = f'{BASE_URL}/sendMessage'
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise e

def get_telegram_file_url(file_id):
    try:
        url = f'{BASE_URL}/getFile'
        response = requests.get(url, params={'file_id': file_id})
        response_json = response.json()
        if response.status_code != 200 or not response_json.get('ok'):
            logger.error(f"Error getting file URL: {response_json}")
            raise Exception(f"Failed to get file URL: {response_json.get('description', 'Unknown error')}")
        file_path = response_json['result']['file_path']
        return f'https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}'
    except Exception as e:
        logger.error(f"Error getting file URL: {e}")
        raise e
