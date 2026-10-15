"""Public JD audit draft intake: never accept a submission without delivery."""
import io
import os
import unittest
from unittest.mock import patch

from app import app, _JD_INTAKE_ATTEMPTS


class DraftIntakeTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        _JD_INTAKE_ATTEMPTS.clear()
        self.client = app.test_client()

    def test_disabled_intake_hides_upload_form(self):
        with patch.dict(os.environ, {'JD_AUDIT_INTAKE_EMAIL': '', 'JD_AUDIT_SMTP_HOST': ''}):
            page = self.client.get('/services/job-description-audit')
            self.assertNotIn(b'type="file"', page.data)
            response = self.client.post('/services/job-description-audit/submit')
            self.assertEqual(response.status_code, 503)

    def test_invalid_attachment_rejected_without_sending(self):
        config = {'JD_AUDIT_INTAKE_EMAIL': 'owner@example.com',
                  'JD_AUDIT_SMTP_HOST': 'smtp.example.com',
                  'JD_AUDIT_SMTP_USER': 'sender@example.com',
                  'JD_AUDIT_SMTP_PASSWORD': 'test-only'}
        with patch.dict(os.environ, config), patch('app.smtplib.SMTP_SSL') as smtp:
            page = self.client.get('/services/job-description-audit')
            self.assertIn(b'type="file"', page.data)
            response = self.client.post('/services/job-description-audit/submit', data={
                'email': 'buyer@example.com', 'role': 'HR Specialist', 'privacy': 'yes',
                'draft': (io.BytesIO(b'not a pdf'), 'job.pdf'),
            })
            self.assertEqual(response.status_code, 400)
            smtp.assert_not_called()

    def test_valid_pdf_delivered_only_to_configured_mailbox(self):
        config = {'JD_AUDIT_INTAKE_EMAIL': 'owner@example.com',
                  'JD_AUDIT_SMTP_HOST': 'smtp.example.com',
                  'JD_AUDIT_SMTP_USER': 'sender@example.com',
                  'JD_AUDIT_SMTP_PASSWORD': 'test-only'}
        with patch.dict(os.environ, config), patch('app.smtplib.SMTP_SSL') as smtp:
            response = self.client.post('/services/job-description-audit/submit', data={
                'email': 'buyer@example.com', 'role': 'HR Specialist', 'privacy': 'yes',
                'draft': (io.BytesIO(b'%PDF-1.4\nexample'), 'job.pdf'),
            })
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'pending manual payment verification', response.data)
            message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            self.assertEqual(message['To'], 'owner@example.com')
            self.assertEqual(message['Reply-To'], 'buyer@example.com')
            self.assertEqual(len(list(message.iter_attachments())), 1)

    def test_mail_failure_never_claims_receipt(self):
        config = {'JD_AUDIT_INTAKE_EMAIL': 'owner@example.com',
                  'JD_AUDIT_SMTP_HOST': 'smtp.example.com',
                  'JD_AUDIT_SMTP_USER': 'sender@example.com',
                  'JD_AUDIT_SMTP_PASSWORD': 'test-only'}
        with patch.dict(os.environ, config), patch('app.smtplib.SMTP_SSL', side_effect=OSError('offline')):
            response = self.client.post('/services/job-description-audit/submit', data={
                'email': 'buyer@example.com', 'role': 'HR Specialist', 'privacy': 'yes',
                'draft': (io.BytesIO(b'%PDF-1.4\nexample'), 'job.pdf'),
            })
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b'Draft received', response.data)


if __name__ == '__main__':
    unittest.main()
