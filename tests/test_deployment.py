import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deploy_render', Path(__file__).parents[1] / 'scripts/deploy-render.py')
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.commit = 'a' * 40
        self.env = patch.dict(os.environ, {'RENDER_API_KEY':'test-key-never-log', 'RENDER_SERVICE_ID':'srv-fixture123', 'KENNY_DEPLOY_COMMIT':self.commit}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def replies(self, commit=None):
        return [
            {'type':'web_service', 'branch':'main', 'serviceDetails':{'url':'https://kenny-fixture.onrender.com'}},
            {'id':'dep-fixture123'},
            {'status':'live', 'commit':{'id':commit or self.commit}},
            {'service':'kenny-api', 'status':'ok'},
        ]

    def test_deploy_waits_for_matching_commit_and_verifies_admin(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / 'summary.md'
            os.environ['GITHUB_STEP_SUMMARY'] = str(summary)
            with patch.object(deployment, 'request_json', side_effect=self.replies()) as api, patch.object(deployment.urllib.request, 'urlopen') as page, patch('sys.stdout', new_callable=io.StringIO) as output:
                page.return_value.__enter__.return_value.status = 200
                page.return_value.__enter__.return_value.read.return_value = b'<script src="/admin/app.js"></script>'
                deployment.deploy()
                self.assertEqual(api.call_args_list[1].args[2]['commitId'], self.commit)
                self.assertIn('/admin/', summary.read_text())
                self.assertNotIn('test-key-never-log', output.getvalue())

    def test_stale_deployment_is_never_announced_as_success(self):
        with patch.object(deployment, 'request_json', side_effect=self.replies('b'*40)):
            with self.assertRaisesRegex(RuntimeError, 'commit differs'):
                deployment.deploy()

    def test_failed_deployment_stops_before_health_checks(self):
        replies = self.replies()[:2] + [{'status':'build_failed'}]
        with patch.object(deployment, 'request_json', side_effect=replies) as api:
            with self.assertRaisesRegex(RuntimeError, 'build_failed'):
                deployment.deploy()
            self.assertEqual(api.call_count, 3)

    def test_missing_credentials_and_untrusted_service_url(self):
        with patch.dict(os.environ, {'RENDER_API_KEY':''}):
            with self.assertRaisesRegex(RuntimeError, 'Set GitHub secret'):
                deployment.configuration()
        for value in ['http://example.com', 'https://user:password@example.com', 'https://example.com/path', 'https://example.com?token=secret']:
            with self.assertRaises(RuntimeError):
                deployment.public_origin(value)


if __name__ == '__main__':
    unittest.main()
