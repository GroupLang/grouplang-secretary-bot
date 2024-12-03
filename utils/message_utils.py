# Hello, provider testing
from typing import Dict, Any

def format_response(transcription: str, summary: str) -> str:
    return f"""*Summary:*
{summary}

*Transcription:*
{transcription}"""

def create_tip_button(conversation_id: str) -> Dict[str, Any]:
    return {
        'inline_keyboard': [[{
            'text': 'Add Tip (1$)',
            'callback_data': f'tip:{conversation_id}'
        }]]
    }
