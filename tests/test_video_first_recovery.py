import os
import unittest
from unittest.mock import patch
from scripts import cinematic_production as cp

class VideoFirstRecoveryTests(unittest.TestCase):
    def test_later_query_video_precedes_first_query_photo(self):
        class Reply:
            def __init__(self, data): self.data = data
            def raise_for_status(self): pass
            def json(self): return self.data
        def get(url, **kwargs):
            if '/videos/' in url:
                q = kwargs['params']['query']
                return Reply({'videos': [] if q == 'specific' else [{
                    'url': 'https://pexels.com/video/1',
                    'video_files': [{'link': 'https://example.test/video.mp4', 'height': 1920, 'width': 1080}]}]})
            self.fail('Photos must not be searched before later-query videos')
        with patch.dict(os.environ, {'PEXELS_API_KEY': 'test'}), patch.object(cp, 'search_queries', return_value=('specific','fallback')), patch.object(cp.requests, 'get', side_effect=get):
            first = next(cp.candidates({}, {}))
        self.assertFalse(first['image'])
        self.assertEqual(first['source'], 'pexels')
