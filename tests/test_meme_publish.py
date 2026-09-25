import json
import tempfile
import unittest
from pathlib import Path
from instagram_factory.api import InstagramAPIError
from instagram_factory.config import Settings
from instagram_factory.pipeline import Pipeline

class MemePublishTests(unittest.TestCase):
    def run_case(self, mode):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            asset = root / 'meme.jpg'
            asset.write_bytes(b'test')
            queue = root / 'queue.json'
            post = dict(id='meme', status='ready', media_type='image', assets=[str(asset)],
                        production_approved=True, on_image_text='короткий мем', caption='мем',
                        rights_status='original', scheduled_at='2026-01-01T00:00:00+00:00',
                        qa=dict.fromkeys(['text','anatomy','identity','crop','rights'],True))
            if mode == 'unapproved': post['production_approved'] = False
            queue.write_text(json.dumps([post]))
            pipe = Pipeline(Settings(access_token='test', user_id='test', asset_base_url='https://example.test',
                            queue_path=queue, autopublish_enabled=True, timezone_name='UTC'))
            class API:
                def content_publishing_limit(self):
                    if mode == 'quota_error': raise InstagramAPIError('no quota')
                    return {'data':[{'quota_usage':100 if mode=='full' else 0,'config':{'quota_total':100}}]}
                def _request(self, method, path, params):
                    if mode == 'uncertain': raise InstagramAPIError('timeout')
                    assert params['caption'] == 'мем'
                    assert json.loads(queue.read_text())[0]['status'] == 'publishing'
                    return {'id':'container'}
                def wait_until_ready(self, container): pass
                def publish_container(self, container): return 'media'
            pipe.api = API()
            if mode=='uncertain':
                with self.assertRaises(InstagramAPIError): pipe.publish_due()
                self.assertEqual(pipe.publish_due()['reason'],'publish_paused_requires_reconciliation')
            else:
                result=pipe.publish_due()
                if mode=='success':
                    self.assertEqual(result['published'],1)
                    self.assertEqual(pipe.publish_due()['published'],0)
                else: self.assertEqual(result['published'],0)
            state=json.loads(queue.read_text())[0]['status']
            self.assertEqual(state, {'success':'published','full':'publish_paused','quota_error':'publish_paused','uncertain':'publishing','unapproved':'ready'}[mode])
    def test_success_no_duplicate(self): self.run_case('success')
    def test_quota_full_pauses(self): self.run_case('full')
    def test_quota_error_pauses(self): self.run_case('quota_error')
    def test_ambiguous_result_no_retry(self): self.run_case('uncertain')
    def test_unapproved_never_published(self): self.run_case('unapproved')
