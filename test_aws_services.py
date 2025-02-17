import unittest
from unittest.mock import patch, MagicMock
from aws_services import AWSServices
import json
import requests
from botocore.exceptions import ClientError

class TestAWSServices(unittest.TestCase):
    @patch('boto3.client')
    def setUp(self, mock_boto3_client):
        # Create separate mocks for s3 and transcribe
        self.mock_s3 = MagicMock()
        self.mock_transcribe = MagicMock()
        
        def mock_client(service_name, region_name=None):
            if service_name == 's3':
                return self.mock_s3
            elif service_name == 'transcribe':
                return self.mock_transcribe
        
        mock_boto3_client.side_effect = mock_client
        self.aws_services = AWSServices(region_name='us-east-1')

    def test_setup_bucket_lifecycle(self):
        # Test successful configuration
        self.aws_services.setup_bucket_lifecycle()
        
        # Verify correct lifecycle configuration
        self.mock_s3.put_bucket_lifecycle_configuration.assert_called_once()
        call_args = self.mock_s3.put_bucket_lifecycle_configuration.call_args[1]
        self.assertEqual(call_args['Bucket'], 'audio-transcribe-temp')
        
        lifecycle_rules = call_args['LifecycleConfiguration']['Rules']
        self.assertEqual(len(lifecycle_rules), 1)
        self.assertEqual(lifecycle_rules[0]['Expiration']['Days'], 1)
        self.assertEqual(lifecycle_rules[0]['Status'], 'Enabled')

    @patch('requests.get')
    def test_transcribe_audio_cleanup(self, mock_requests_get):
        # Mock successful file upload
        self.mock_s3.upload_file.return_value = None
        
        # Mock successful transcription job
        self.mock_transcribe.get_transcription_job.return_value = {
            'TranscriptionJob': {
                'TranscriptionJobStatus': 'COMPLETED',
                'Transcript': {'TranscriptFileUri': 'https://example.com/transcript.json'}
            }
        }
        
        # Mock successful transcript download
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'results': {
                'transcripts': [{'transcript': 'Hello world'}]
            }
        }
        mock_requests_get.return_value = mock_response
        
        # Test transcription with cleanup
        result = self.aws_services.transcribe_audio('test.wav')
        
        # Verify the transcription result
        self.assertEqual(result, 'Hello world')
        
        # Verify cleanup was attempted
        self.mock_s3.delete_object.assert_called_once_with(
            Bucket='audio-transcribe-temp',
            Key='temp/test.wav'
        )

    def test_transcribe_audio_failure(self):
        # Mock failed upload
        self.mock_s3.upload_file.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchBucket', 'Message': 'The bucket does not exist'}},
            'upload_file'
        )
        
        # Test transcription with failure
        result = self.aws_services.transcribe_audio('test.wav')
        
        # Verify the failure result
        self.assertIsNone(result)
        
        # Verify cleanup was not attempted since upload failed
        self.mock_s3.delete_object.assert_not_called()

if __name__ == '__main__':
    unittest.main()