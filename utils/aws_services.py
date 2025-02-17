import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self, bucket_name="audiotranscribetemp"):
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name
        self._setup_lifecycle_policy()

    def _setup_lifecycle_policy(self):
        """
        Sets up a lifecycle policy for the S3 bucket to automatically delete objects
        after 24 hours, regardless of their status.
        """
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'DeleteTempAudioFiles',
                        'Status': 'Enabled',
                        'Filter': {
                            'Prefix': ''  # Apply to all objects
                        },
                        'Expiration': {
                            'Days': 1  # Delete objects after 24 hours
                        }
                    }
                ]
            }
            
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket_name,
                LifecycleConfiguration=lifecycle_config
            )
            logger.info(f"Successfully set up lifecycle policy for bucket {self.bucket_name}")
        except ClientError as e:
            logger.error(f"Failed to set up lifecycle policy: {str(e)}")
            raise

    def upload_audio(self, file_path, s3_key):
        """
        Uploads an audio file to S3 with error handling.
        """
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            logger.info(f"Successfully uploaded {file_path} to {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {file_path}: {str(e)}")
            raise

    def delete_audio(self, s3_key):
        """
        Deletes an audio file from S3 with error handling.
        Note: With lifecycle policy in place, this is a backup method
        for immediate deletion when needed.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {s3_key}: {str(e)}")
            raise

    def get_audio_url(self, s3_key):
        """
        Generates a pre-signed URL for the audio file.
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=3600  # URL expires in 1 hour
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {s3_key}: {str(e)}")
            raise