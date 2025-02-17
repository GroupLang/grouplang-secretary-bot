import unittest
from unittest.mock import patch, MagicMock
from aws_services import AWSServices
import boto3

class TestAWSServices(unittest.TestCase):
    @patch('boto3.client')
    def setUp(self, mock_boto3_client):
        # Configure mock responses
        self.mock_s3 = MagicMock()
        self.mock_transcribe = MagicMock()
        self.mock_cloudwatch = MagicMock()
        
        def mock_client(service, region_name=None):
            if service == 's3':
                return self.mock_s3
            elif service == 'cloudwatch':
                return self.mock_cloudwatch
            return self.mock_transcribe
            
        mock_boto3_client.side_effect = mock_client
        self.aws_services = AWSServices('us-east-1')

    def test_setup_bucket_lifecycle(self):
        # Test successful configuration
        result = self.aws_services.setup_bucket_lifecycle()
        
        # Verify
        self.assertTrue(result)
        self.mock_s3.put_bucket_lifecycle_configuration.assert_called_once()
        
        # Verify the lifecycle configuration
        call_args = self.mock_s3.put_bucket_lifecycle_configuration.call_args[1]
        self.assertEqual(call_args['Bucket'], 'audio-transcribe-temp')
        self.assertEqual(call_args['LifecycleConfiguration']['Rules'][0]['Expiration']['Days'], 1)

    def test_transcribe_audio_success(self):
        # Mock successful transcription
        self.mock_transcribe.get_transcription_job.return_value = {
            'TranscriptionJob': {
                'TranscriptionJobStatus': 'COMPLETED',
                'Transcript': {
                    'TranscriptFileUri': 'https://example.com/transcript.json'
                }
            }
        }

        # Test transcription
        result = self.aws_services.transcribe_audio('test.mp3', 'test-job')
        
        # Verify
        self.assertEqual(result, 'https://example.com/transcript.json')
        self.mock_s3.upload_file.assert_called_once()
        self.mock_s3.delete_object.assert_called_once()
        self.mock_transcribe.start_transcription_job.assert_called_once()

    def test_transcribe_audio_failure(self):
        # Mock failed transcription
        self.mock_transcribe.get_transcription_job.return_value = {
            'TranscriptionJob': {
                'TranscriptionJobStatus': 'FAILED',
                'FailureReason': 'Audio file format not supported'
            }
        }

        # Test transcription failure
        with self.assertRaises(Exception) as context:
            self.aws_services.transcribe_audio('test.mp3', 'test-job')
        
        # Verify error message
        self.assertIn('Audio file format not supported', str(context.exception))
        
        # Verify cleanup was attempted even after failure
        self.mock_s3.upload_file.assert_called_once()
        self.mock_s3.delete_object.assert_called_once()
        self.mock_transcribe.start_transcription_job.assert_called_once()

    def test_metrics_on_success(self):
        """Test that metrics are published correctly on successful transcription"""
        # Mock successful transcription
        self.mock_transcribe.get_transcription_job.return_value = {
            'TranscriptionJob': {
                'TranscriptionJobStatus': 'COMPLETED',
                'Transcript': {
                    'TranscriptFileUri': 'https://example.com/transcript.json'
                }
            }
        }

        # Execute transcription
        self.aws_services.transcribe_audio('test.mp3', 'test-job')

        # Verify metrics were published
        expected_metrics = [
            ('FileUploads', 1, 'Count'),
            ('StorageUsage', 1, 'Bytes'),
            ('TranscriptionJobsStarted', 1, 'Count'),
            ('TranscriptionJobsSucceeded', 1, 'Count'),
            ('FilesDeleted', 1, 'Count')
        ]

        for metric_name, value, unit in expected_metrics:
            self.mock_cloudwatch.put_metric_data.assert_any_call(
                Namespace='AudioTranscriptionService',
                MetricData=[{
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': unit,
                    'Dimensions': [{
                        'Name': 'Bucket',
                        'Value': 'audio-transcribe-temp'
                    }]
                }]
            )

    def test_metrics_on_failure(self):
        """Test that metrics are published correctly on transcription failure"""
        # Mock failed transcription
        self.mock_transcribe.get_transcription_job.return_value = {
            'TranscriptionJob': {
                'TranscriptionJobStatus': 'FAILED',
                'FailureReason': 'Audio file format not supported'
            }
        }

        # Execute transcription (should raise exception)
        with self.assertRaises(Exception):
            self.aws_services.transcribe_audio('test.mp3', 'test-job')

        # Verify metrics were published
        expected_metrics = [
            ('FileUploads', 1, 'Count'),
            ('StorageUsage', 1, 'Bytes'),
            ('TranscriptionJobsStarted', 1, 'Count'),
            ('TranscriptionJobsFailed', 1, 'Count'),
            ('FilesDeleted', 1, 'Count')
        ]

        for metric_name, value, unit in expected_metrics:
            self.mock_cloudwatch.put_metric_data.assert_any_call(
                Namespace='AudioTranscriptionService',
                MetricData=[{
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': unit,
                    'Dimensions': [{
                        'Name': 'Bucket',
                        'Value': 'audio-transcribe-temp'
                    }]
                }]
            )

if __name__ == '__main__':
    unittest.main()