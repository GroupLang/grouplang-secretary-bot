import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class AWSServices:
    def __init__(self, region_name='us-east-1'):
        self.region_name = region_name
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.transcribe_client = boto3.client('transcribe', region_name=region_name)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region_name)
        self.TEMP_BUCKET = 'audio-transcribe-temp'

    def _publish_metric(self, metric_name, value, unit='Count'):
        """Publish CloudWatch metrics for monitoring"""
        try:
            self.cloudwatch_client.put_metric_data(
                Namespace='AudioTranscriptionService',
                MetricData=[{
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': unit,
                    'Dimensions': [{
                        'Name': 'Bucket',
                        'Value': self.TEMP_BUCKET
                    }]
                }]
            )
            logger.info(f"Published metric {metric_name}: {value} {unit}")
        except Exception as e:
            logger.warning(f"Failed to publish metric {metric_name}: {str(e)}")

    def setup_bucket_lifecycle(self):
        """Configure lifecycle policy to delete objects after 24 hours"""
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'Delete after 24 hours',
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

    def transcribe_audio(self, audio_file_path, job_name):
        """
        Upload audio file to S3 and transcribe it with proper error handling,
        cleanup, and metrics tracking
        """
        s3_key = f"temp_audio/{job_name}"
        try:
            # Upload to S3
            self.s3_client.upload_file(
                audio_file_path,
                self.TEMP_BUCKET,
                s3_key
            )
            logger.info(f"Successfully uploaded {audio_file_path} to S3")
            self._publish_metric('FileUploads', 1)
            self._publish_metric('StorageUsage', 1, 'Bytes')

            # Start transcription job
            job_uri = f"s3://{self.TEMP_BUCKET}/{s3_key}"
            self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': job_uri},
                MediaFormat='mp3',  # Adjust based on your audio format
                LanguageCode='en-US'  # Adjust based on your needs
            )
            self._publish_metric('TranscriptionJobsStarted', 1)

            # Wait for completion
            while True:
                status = self.transcribe_client.get_transcription_job(
                    TranscriptionJobName=job_name
                )
                job_status = status['TranscriptionJob']['TranscriptionJobStatus']
                
                if job_status in ['COMPLETED', 'FAILED']:
                    break

            # Handle job completion and track outcome
            if job_status == 'COMPLETED':
                result_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                self._publish_metric('TranscriptionJobsSucceeded', 1)
            else:
                error_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown error')
                self._publish_metric('TranscriptionJobsFailed', 1)
                error_msg = f"Transcription failed: {error_reason}"

            # Cleanup temp file regardless of transcription success
            try:
                self.s3_client.delete_object(
                    Bucket=self.TEMP_BUCKET,
                    Key=s3_key
                )
                logger.info(f"Cleaned up temporary file {s3_key}")
                self._publish_metric('FilesDeleted', 1)
            except ClientError as e:
                logger.warning(f"Failed to delete temporary file {s3_key}: {str(e)}")
                self._publish_metric('FileCleanupFailures', 1)

            if job_status == 'COMPLETED':
                return result_uri
            else:
                raise Exception(error_msg)

        except ClientError as e:
            logger.error(f"AWS operation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Transcription process failed: {str(e)}")
            raise