import boto3
import logging
import time
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class AWSServices:
    def __init__(self, region_name='us-east-1'):
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.transcribe_client = boto3.client('transcribe', region_name=region_name)
        self.TEMP_BUCKET = 'audio-transcribe-temp'
        self.region_name = region_name

    def setup_bucket_lifecycle(self):
        """Configure lifecycle policy to delete objects after 24 hours"""
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'DeleteAfter24Hours',
                        'Status': 'Enabled',
                        'Prefix': '',
                        'Expiration': {'Days': 1}
                    }
                ]
            }
            
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.TEMP_BUCKET,
                LifecycleConfiguration=lifecycle_config
            )
            logger.info(f"Successfully configured lifecycle policy for bucket {self.TEMP_BUCKET}")
            return True
        except ClientError as e:
            logger.error(f"Failed to configure lifecycle policy: {str(e)}")
            return False

    def transcribe_audio(self, audio_file_path, language_code='en-US'):
        """
        Transcribe audio file with proper error handling and cleanup
        Returns: Transcription text or None if failed
        """
        try:
            # Generate a unique S3 key for the audio file
            file_name = audio_file_path.split('/')[-1]
            s3_key = f"temp/{file_name}"
            
            # Upload file to S3
            try:
                self.s3_client.upload_file(
                    audio_file_path, 
                    self.TEMP_BUCKET, 
                    s3_key
                )
                logger.info(f"Successfully uploaded {file_name} to S3")
            except ClientError as e:
                logger.error(f"Failed to upload file to S3: {str(e)}")
                return None

            # Start transcription job
            job_name = f"transcribe_{file_name.replace('.', '_')}"
            s3_uri = f"s3://{self.TEMP_BUCKET}/{s3_key}"
            
            try:
                self.transcribe_client.start_transcription_job(
                    TranscriptionJobName=job_name,
                    Media={'MediaFileUri': s3_uri},
                    MediaFormat=file_name.split('.')[-1],
                    LanguageCode=language_code
                )
                
                # Wait for completion
                while True:
                    status = self.transcribe_client.get_transcription_job(
                        TranscriptionJobName=job_name
                    )
                    if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                        break
                    time.sleep(5)

                if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
                    transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                    # Process transcript and return text
                    return self._get_transcript_text(transcript_uri)
                else:
                    logger.error(f"Transcription job failed: {job_name}")
                    return None

            except ClientError as e:
                logger.error(f"Transcription error: {str(e)}")
                return None
            
            finally:
                # Always try to clean up the temporary file
                try:
                    self.s3_client.delete_object(
                        Bucket=self.TEMP_BUCKET,
                        Key=s3_key
                    )
                    logger.info(f"Cleaned up temporary file: {s3_key}")
                except ClientError as e:
                    logger.warning(f"Failed to delete temporary file {s3_key}: {str(e)}")
                    # Don't raise the error as the lifecycle policy will clean it up

        except Exception as e:
            logger.error(f"Unexpected error in transcribe_audio: {str(e)}")
            return None

    def _get_transcript_text(self, transcript_uri):
        """Helper method to get transcript text from URI"""
        import requests
        try:
            response = requests.get(transcript_uri)
            response.raise_for_status()
            return response.json()['results']['transcripts'][0]['transcript']
        except Exception as e:
            logger.error(f"Failed to get transcript text: {str(e)}")
            return None