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

    def upload_audio(self, file_path, object_name):
        """
        Upload an audio file to S3.
        """
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, object_name)
            logger.info(f"Successfully uploaded {object_name} to {self.bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {object_name}: {str(e)}")
            return False

    def delete_audio(self, object_name):
        """
        Delete an audio file from S3.
        Note: With lifecycle policy in place, this is optional but recommended
        for immediate cleanup after successful processing.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"Successfully deleted {object_name} from {self.bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {object_name}: {str(e)}")
            return False