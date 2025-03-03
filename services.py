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
                # Configure lifecycle policy for automatic cleanup
                self.configure_lifecycle_policy(bucket_name)
            else:
                raise

    def configure_lifecycle_policy(self, bucket_name):
        """Configure lifecycle policy to delete objects after 24 hours"""
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'DeleteOldAudioFiles',
                        'Status': 'Enabled',
                        'Prefix': '',  # Apply to all objects
                        'Expiration': {'Days': 1},  # Delete after 24 hours
                        'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': 1}
                    }
                ]
            }
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration=lifecycle_config
            )
            logger.info(f"Configured lifecycle policy for bucket: {bucket_name}")
        except ClientError as e:
            logger.error(f"Error configuring lifecycle policy: {e}")
            raise

    def upload_file_to_s3(self, file_content, bucket_name, object_key):
        """Upload a file to S3 with retry logic and proper error handling"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Validate input
                if not file_content:
                    raise ValueError("Empty file content provided")
                
                if not isinstance(file_content, bytes):
                    raise ValueError("File content must be bytes")
                
                # Create file-like object in memory
                file_obj = BytesIO(file_content)
                
                # Upload with specific configuration
                self.s3_client.upload_fileobj(
                    file_obj,
                    bucket_name,
                    object_key,
                    ExtraArgs={
                        'ContentType': 'audio/ogg',  # Set appropriate content type
                        'ServerSideEncryption': 'AES256'  # Enable server-side encryption
                    }
                )
                
                logger.info(f"Successfully uploaded {len(file_content)} bytes to s3://{bucket_name}/{object_key}")
                return f's3://{bucket_name}/{object_key}'
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_msg = e.response['Error']['Message']
                logger.error(f"S3 upload error (attempt {attempt + 1}/{max_retries}): {error_code} - {error_msg}")
                
                # Don't retry certain errors
                if error_code in ['AccessDenied', 'InvalidBucketName', 'NoSuchBucket']:
                    raise Exception(f"S3 upload failed: {error_msg}") from e
                
                if attempt == max_retries - 1:
                    raise Exception("S3 upload failed after all retries") from e
                    
            except Exception as e:
                logger.error(f"Unexpected error during S3 upload (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise Exception("Unexpected error during S3 upload") from e
            
            time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

    def delete_file_from_s3(self, bucket_name, object_key):
        """Delete a file from S3 with retry logic and proper error handling"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Check if object exists before attempting deletion
                try:
                    self.s3_client.head_object(Bucket=bucket_name, Key=object_key)
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        logger.warning(f"Object s3://{bucket_name}/{object_key} does not exist")
                        return
                    raise
                
                # Perform deletion
                self.s3_client.delete_object(Bucket=bucket_name, Key=object_key)
                
                # Verify deletion
                try:
                    self.s3_client.head_object(Bucket=bucket_name, Key=object_key)
                    raise Exception("Object still exists after deletion")
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        logger.info(f"Successfully deleted s3://{bucket_name}/{object_key}")
                        return
                    raise
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_msg = e.response['Error']['Message']
                logger.error(f"S3 deletion error (attempt {attempt + 1}/{max_retries}): {error_code} - {error_msg}")
                
                # Don't retry certain errors
                if error_code in ['AccessDenied', 'NoSuchBucket']:
                    raise Exception(f"S3 deletion failed: {error_msg}") from e
                
                if attempt == max_retries - 1:
                    raise Exception("S3 deletion failed after all retries") from e
                    
            except Exception as e:
                logger.error(f"Unexpected error during S3 deletion (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise Exception("Unexpected error during S3 deletion") from e
            
            time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

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

    def transcribe_audio(self, file_url: str) -> str:
        object_key = None
        try:
            # Create or confirm S3 bucket existence
            try:
                self.aws_services.create_s3_bucket_if_not_exists(self.bucket_name)
                logger.info(f"S3 Bucket created/confirmed: {self.bucket_name}")
            except ClientError as e:
                logger.error(f"Failed to create/confirm S3 bucket: {e}")
                raise Exception("S3 bucket configuration failed") from e

            # Download audio file
            try:
                audio_content = self._download_audio(file_url)
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download audio from URL {file_url}: {e}")
                raise Exception("Audio download failed") from e

            # Upload to S3
            try:
                object_key = f'audio_{uuid.uuid4()}.ogg'
                s3_uri = self.aws_services.upload_file_to_s3(audio_content, self.bucket_name, object_key)
                logger.info(f"Audio file uploaded successfully. S3 URI: {s3_uri}")
            except ClientError as e:
                logger.error(f"Failed to upload audio to S3: {e}")
                raise Exception("S3 upload failed") from e

            # Start transcription job
            try:
                job_name = f"whisper_job_{int(time.time())}"
                self.aws_services.start_transcription_job(job_name, s3_uri)
                logger.info(f"Transcription job started: {job_name}")
            except ClientError as e:
                logger.error(f"Failed to start transcription job: {e}")
                raise Exception("Transcription job start failed") from e

            # Wait for and get transcription
            try:
                transcription = self._wait_for_transcription(job_name)
                logger.info("Transcription completed successfully")
            except Exception as e:
                logger.error(f"Transcription process failed: {e}")
                raise Exception("Transcription process failed") from e

            return transcription

        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise

        finally:
            # Cleanup: Always try to delete the temporary audio file if it was created
            if object_key:
                try:
                    self.aws_services.delete_file_from_s3(self.bucket_name, object_key)
                    logger.info(f"Cleaned up temporary audio file: {object_key}")
                except ClientError as e:
                    logger.warning(f"Failed to delete temporary audio file {object_key}: {e}")
                    # Don't raise exception here as it's just cleanup

    def _download_audio(self, file_url: str) -> bytes:
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.get(file_url, timeout=30)  # 30 seconds timeout
                response.raise_for_status()
                
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith(('audio/', 'video/')):
                    logger.warning(f"Unexpected content type: {content_type}")
                
                content_length = len(response.content)
                if content_length == 0:
                    raise ValueError("Downloaded file is empty")
                
                logger.info(f"Successfully downloaded audio file: {content_length} bytes")
                return response.content
                
            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout downloading audio (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise Exception("Audio download timed out after all retries") from e
                    
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else 'unknown'
                logger.error(f"HTTP error {status_code} downloading audio (attempt {attempt + 1}/{max_retries}): {e}")
                if status_code in [404, 401, 403]:  # Don't retry client errors
                    raise Exception(f"Audio file not accessible (HTTP {status_code})") from e
                if attempt == max_retries - 1:
                    raise Exception("Audio download failed after all retries") from e
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error downloading audio (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise Exception("Network error during audio download") from e
            
            time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

    def _wait_for_transcription(self, job_name: str) -> str:
        max_retries = 60  # 5 minutes timeout (5 seconds * 60)
        retries = 0
        
        while retries < max_retries:
            try:
                status = self.aws_services.get_transcription_job_status(job_name)
                job_status = status['TranscriptionJob']['TranscriptionJobStatus']
                
                if job_status == 'COMPLETED':
                    try:
                        transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                        result = requests.get(transcript_uri)
                        result.raise_for_status()
                        return result.json()['results']['transcripts'][0]['transcript']
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Failed to fetch transcript from URI {transcript_uri}: {e}")
                        raise Exception("Failed to fetch completed transcript") from e
                    except (KeyError, IndexError) as e:
                        logger.error(f"Invalid transcript format: {e}")
                        raise Exception("Invalid transcript format in response") from e
                
                elif job_status == 'FAILED':
                    failure_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown reason')
                    logger.error(f"Transcription job failed: {failure_reason}")
                    raise Exception(f"Transcription job failed: {failure_reason}")
                
                elif job_status in ['IN_PROGRESS', 'QUEUED']:
                    logger.debug(f"Transcription job status: {job_status}")
                    retries += 1
                    time.sleep(5)
                    continue
                
                else:
                    logger.error(f"Unknown transcription job status: {job_status}")
                    raise Exception(f"Unknown transcription job status: {job_status}")
                
            except ClientError as e:
                logger.error(f"AWS error while checking transcription status: {e}")
                raise Exception("Failed to check transcription status") from e
        
        logger.error(f"Transcription job timed out after {max_retries * 5} seconds")
        raise Exception("Transcription job timed out")

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
