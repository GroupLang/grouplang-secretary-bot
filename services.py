import boto3
from typing import Optional, Tuple, Dict
import requests
import time
import uuid
import logging
from io import BytesIO
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class AWSServices:
    def __init__(self, region_name='us-east-1'):
        self.region_name = region_name
        self.s3_client = boto3.client('s3', region_name=self.region_name)
        self.transcribe_client = boto3.client('transcribe', region_name=self.region_name)

    def create_s3_bucket_if_not_exists(self, bucket_name):
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region_name}
                )
            else:
                raise

    def upload_file_to_s3(self, file_content, bucket_name, object_key):
        self.s3_client.upload_fileobj(BytesIO(file_content), bucket_name, object_key)
        return f's3://{bucket_name}/{object_key}'

    def delete_file_from_s3(self, bucket_name, object_key):
        self.s3_client.delete_object(Bucket=bucket_name, Key=object_key)

    def start_transcription_job(self, job_name, media_uri, media_format='ogg', language_code='en-US'):
        return self.transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': media_uri},
            MediaFormat=media_format,
            LanguageCode=language_code,
            Settings={
                'ShowSpeakerLabels': True,
                'MaxSpeakerLabels': 2,
                'ChannelIdentification': True
            }
        )

    def get_transcription_job_status(self, job_name):
        return self.transcribe_client.get_transcription_job(TranscriptionJobName=job_name)

class AudioTranscriber:
    def __init__(self, aws_services: AWSServices):
        self.aws_services = aws_services
        self.bucket_name = 'audio-transcribe-temp'

    def transcribe_audio(self, file_url: str, language_code: str = 'en-US') -> str:
        try:
            self.aws_services.create_s3_bucket_if_not_exists(self.bucket_name)
            logger.info(f"S3 Bucket created/confirmed: {self.bucket_name}")

            audio_content = self._download_audio(file_url)
            object_key = f'audio_{uuid.uuid4()}.ogg'
            s3_uri = self.aws_services.upload_file_to_s3(audio_content, self.bucket_name, object_key)
            logger.info(f"S3 URI: {s3_uri}")

            job_name = f"whisper_job_{int(time.time())}"
            self.aws_services.start_transcription_job(job_name, s3_uri, language_code=language_code)
            logger.info(f"Transcription job started: {job_name}")

            transcription = self._wait_for_transcription(job_name)
            self.aws_services.delete_file_from_s3(self.bucket_name, object_key)

            return transcription
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise

    def _download_audio(self, file_url: str) -> bytes:
        response = requests.get(file_url)
        response.raise_for_status()
        return response.content

    def _wait_for_transcription(self, job_name: str) -> str:
        while True:
            status = self.aws_services.get_transcription_job_status(job_name)
            if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                break
            time.sleep(5)

        if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
            result = requests.get(status['TranscriptionJob']['Transcript']['TranscriptFileUri'])
            return result.json()['results']['transcripts'][0]['transcript']
        else:
            raise Exception("Transcription failed")

class TextSummarizer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://api.marketrouter.ai/v1'

    def summarize_text(self, text: str) -> Tuple[Optional[str], str]:
        try:
            conversation_id = self._submit_instance(text)
            logger.info(f"Instance submitted with conversation_id: {conversation_id}")
            
            summary = self._fetch_messages(conversation_id)
            if summary:
                logger.info(f"Summary fetched for conversation_id: {conversation_id}")
            else:
                logger.warning(f"No summary available for conversation_id: {conversation_id}")
            
            return summary, conversation_id
        except Exception as e:
            logger.error(f"An error occurred in summarize_text: {e}")
            raise

    def submit_reward(self, conversation_id: str, reward_amount: float) -> None:
        try:
            response = requests.put(
                f'{self.base_url}/instances/{conversation_id}/report-reward',
                headers=self._get_headers(),
                json={'gen_reward': reward_amount}
            )
            response.raise_for_status()
            logger.info(f"Reward submitted successfully for conversation_id: {conversation_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while submitting reward: {e}")
            raise

    def _submit_instance(self, text: str) -> str:
        instance_params = {
            "messages": [{"role": "user", "content": f"Summarize this text: {text}"}],
            "model": "gpt-4o",
            "background": "Summarize this text",
            "max_credit_per_instance": 0.01,
            "instance_timeout": 5,
            "gen_reward_timeout": 60,
            "percentage_reward": 1,
        }

        try:
            response = requests.post(
                f'{self.base_url}/instances',
                headers=self._get_headers(),
                json=instance_params
            )
            response.raise_for_status()
            conversation_id = response.json().get('id')
            if not conversation_id:
                raise ValueError("Response does not contain 'id' field")
            
            time.sleep(instance_params['instance_timeout'] + 5)
            return conversation_id
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while submitting the instance: {e}")
            raise

    def _fetch_messages(self, conversation_id: str) -> Optional[str]:
        try:
            response = requests.get(
                f'{self.base_url}/chat/completions/{conversation_id}',
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and data:
                last_item = data[-1]
                if ('response' in last_item and 'choices' in last_item['response'] and 
                    last_item['response']['choices']):
                    last_response = last_item['response']['choices'][-1].get('message', {})
                    return last_response.get('content', '')
            
            logger.warning(f"No valid summary found for conversation_id: {conversation_id}")
            return None
        except requests.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
            raise
        except Exception as err:
            logger.error(f"An error occurred: {err}")
            raise

    def _get_headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key
        }
