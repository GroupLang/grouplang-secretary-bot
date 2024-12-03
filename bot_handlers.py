import logging
import os
from typing import Dict, Any
from services import AWSServices, AudioTranscriber, TextSummarizer
from utils.telegram_utils import send_message, get_telegram_file_url
from utils.message_utils import format_response, create_tip_button

logger = logging.getLogger(__name__)

# Initialize services
aws_services = AWSServices()
audio_transcriber = AudioTranscriber(aws_services)
text_summarizer = TextSummarizer(os.environ.get('MARKETROUTER_API_KEY'))

def handle_update(update: Dict[str, Any]) -> None:
    if 'message' in update:
        handle_message(update['message'])
    elif 'callback_query' in update:
        handle_callback_query(update['callback_query'])

def handle_message(message: Dict[str, Any]) -> None:
    chat_id = message['chat']['id']
    logger.info(f"Received message: {message}")

    if 'voice' in message:
        handle_voice_message(message, chat_id)

def handle_voice_message(message: Dict[str, Any], chat_id: int) -> None:
    try:
        file_id = message['voice']['file_id']
        file_url = get_telegram_file_url(file_id)
        
        transcription = audio_transcriber.transcribe_audio(file_url, language_code='en-US')
        summary, conversation_id = text_summarizer.summarize_text(transcription)
        
        logger.info(f"Processed voice message: file_id={file_id}, "
                    f"transcription_length={len(transcription)}, "
                    f"summary_length={len(summary)}")
        
        response = format_response(transcription, summary)
        reply_markup = create_tip_button(conversation_id)
        
        send_message(chat_id, response, reply_markup=reply_markup, 
                     reply_to_message_id=message.get('message_id'))
    except Exception as e:
        handle_error(chat_id, e, message.get('message_id'))

def handle_callback_query(callback_query: Dict[str, Any]) -> None:
    chat_id = callback_query['message']['chat']['id']
    callback_data = callback_query['data']
    
    if callback_data.startswith('tip:'):
        conversation_id = callback_data.split(':')[1]
        handle_tip(chat_id, conversation_id)

def handle_tip(chat_id: int, conversation_id: str) -> None:
    try:
        if conversation_id:
            text_summarizer.submit_reward(conversation_id, 0.01)
            send_message(chat_id, "Thank you for your tip! We've added a 1$ reward.")
        else:
            send_message(chat_id, "Sorry, we couldn't process your tip at this time.")
    except Exception as e:
        handle_error(chat_id, e)

def handle_error(chat_id: int, error: Exception, reply_to_message_id: int = None) -> None:
    error_message = f"An error occurred: {str(error)}"
    logger.error(error_message, exc_info=True)
    send_message(chat_id, error_message, reply_to_message_id=reply_to_message_id)
