
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents"))

# Mock phi module if missing
try:
    import phi
except ImportError:
    mock_phi = MagicMock()
    sys.modules["phi"] = mock_phi
    sys.modules["phi.agent"] = mock_phi
    sys.modules["phi.model"] = mock_phi
    sys.modules["phi.model.ollama"] = mock_phi
    
from agents.specialized.voice_cloning import clone_voice

class TestVoiceCloning(unittest.TestCase):

    @patch('agents.specialized.voice_cloning.requests.post')
    def test_clone_voice_success(self, mock_post):
        # Mock Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake_audio_bytes"
        mock_post.return_value = mock_response

        # Call Tool
        result = clone_voice(text="Hello World", reference_audio_path=None)
        
        # Verify
        self.assertIsInstance(result, str)
        
        # Verify File Creation (and cleanup)
        # Extract filename from result
        import re
        self.assertTrue(os.path.exists(result))
        os.remove(result) # Cleanup

    @patch('agents.specialized.voice_cloning.requests.post')
    def test_clone_voice_failure(self, mock_post):
        # Mock Failure
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        # Call Tool
        result = clone_voice(text="Fail me")
        
        # Verify
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
