#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

import mobile_api
import server
import scripts.fcm_push as fcm_push
import scripts.send_reminders as send_reminders


class TestMobileBackend(unittest.TestCase):
    def test_cors_origins(self):
        # 1. Native mobile and localhost origins
        self.assertEqual(mobile_api.resolve_cors_origin('capacitor://localhost'), 'capacitor://localhost')
        self.assertEqual(mobile_api.resolve_cors_origin('ionic://localhost'), 'ionic://localhost')
        self.assertEqual(mobile_api.resolve_cors_origin('http://localhost'), 'http://localhost')
        self.assertEqual(mobile_api.resolve_cors_origin('https://localhost'), 'https://localhost')
        self.assertEqual(mobile_api.resolve_cors_origin('http://localhost:3000'), 'http://localhost:3000')

        # 2. CORS headers
        headers_dict = dict(mobile_api.cors_headers('capacitor://localhost'))
        self.assertEqual(headers_dict['Access-Control-Allow-Origin'], 'capacitor://localhost')
        self.assertIn('Authorization', headers_dict['Access-Control-Allow-Headers'])
        self.assertIn('OPTIONS', headers_dict['Access-Control-Allow-Methods'])

    def test_jwt_bearer_token(self):
        os.environ['API_TOKEN_SECRET'] = 'test-secret-key-with-minimum-32-characters-length'
        token = mobile_api.issue_token('testuser')
        self.assertTrue(isinstance(token, str) and len(token) > 20)

        # Token verification
        subject = mobile_api.verify_token(token)
        self.assertEqual(subject, 'testuser')

        # Tampered token check returns None
        tampered = token[:-4] + 'xxxx'
        self.assertIsNone(mobile_api.verify_token(tampered))

    def test_fcm_subscription_routing(self):
        # Native FCM subscription
        sub_fcm = {'fcm_token': 'fcm_sample_token_123', 'platform': 'android'}
        self.assertTrue(send_reminders.is_fcm_subscription(sub_fcm))

        sub_ios = {'fcm_token': 'fcm_sample_token_ios', 'platform': 'ios'}
        self.assertTrue(send_reminders.is_fcm_subscription(sub_ios))

        # Web Push subscription (pywebpush)
        sub_web = {'endpoint': 'https://fcm.googleapis.com/fcm/send/xyz', 'keys': {'auth': '123', 'p256dh': '456'}}
        self.assertFalse(send_reminders.is_fcm_subscription(sub_web))

    def test_fcm_push_dry_run_and_status(self):
        # Without credentials, returns STATUS_NOT_CONFIGURED gracefully
        status = fcm_push.send_fcm_notification('invalid_token', 'Test Title', 'Test Body')
        self.assertIn(status, (fcm_push.STATUS_NOT_CONFIGURED, fcm_push.STATUS_ERROR))


if __name__ == '__main__':
    unittest.main()
