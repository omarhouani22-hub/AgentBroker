import unittest
from unittest.mock import patch
import app


class DiscontinuedJobAuditTest(unittest.TestCase):
    def test_retired_endpoints_stay_unavailable(self):
        client = app.app.test_client()
        with patch('app.model_call') as model:
            for path, method in [('/services/job-description-audit', 'get'),
                                 ('/offers/jd-audit/preview', 'post'),
                                 ('/offers/jd-audit/draft', 'post'),
                                 ('/offers/jd-audit/operator-dashboard', 'get'),
                                 ('/offers/jd-audit/operator-queue-preview', 'get')]:
                response = getattr(client, method)(path)
                self.assertEqual(response.status_code, 410, path)
                self.assertIn('discontinued', response.get_json()['error'])
            model.assert_not_called()


if __name__ == '__main__': unittest.main()
