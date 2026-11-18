#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/fcm_push.py
Firebase Cloud Messaging (firebase-admin) ile Android/iOS native push gonderimi.
pywebpush yalnizca tarayici (web) abonelikleri icin kalir; mobil cihazlar bu modulu kullanir.

Kimlik bilgisi (sirayla):
  1. FIREBASE_SERVICE_ACCOUNT_JSON  -> servis hesabi JSON'u (duz metin ya da base64)
  2. GOOGLE_APPLICATION_CREDENTIALS -> JSON dosya yolu

Hicbir log satirinda FCM token'inin tamami yazilmaz.

Manuel test:
  python3 scripts/fcm_push.py --token <FCM_TOKEN> [--dry-run]
"""

import argparse
import base64
import json
import logging
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import admin_logger
except ImportError:
    admin_logger = None

logger = logging.getLogger('FcmPush')

STATUS_SENT = 'sent'
STATUS_UNREGISTERED = 'unregistered'
STATUS_NOT_CONFIGURED = 'not_configured'
STATUS_ERROR = 'error'

_APP_NAME = 'mytakip-fcm'
_app = None
_app_lock = threading.Lock()


class FcmNotConfigured(Exception):
    pass


def _short(token):
    return (token[:6] + '...') if token else '(bos)'


def _service_account_info():
    raw = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '').strip()
    if not raw:
        return None
    if not raw.startswith('{'):
        raw = base64.b64decode(raw).decode('utf-8')
    return json.loads(raw)


def _get_app():
    global _app
    with _app_lock:
        if _app is not None:
            return _app
        try:
            import firebase_admin
            from firebase_admin import credentials
        except ImportError:
            raise FcmNotConfigured("firebase-admin kurulu degil (pip install firebase-admin)")
        info = _service_account_info()
        if info is not None:
            cred = credentials.Certificate(info)
        elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            cred = credentials.ApplicationDefault()
        else:
            raise FcmNotConfigured('FIREBASE_SERVICE_ACCOUNT_JSON veya GOOGLE_APPLICATION_CREDENTIALS tanimli degil')
        try:
            _app = firebase_admin.get_app(_APP_NAME)
        except ValueError:
            _app = firebase_admin.initialize_app(cred, name=_APP_NAME)
        return _app


def send_fcm_notification(token, title, body, data=None, dry_run=False):
    if not token:
        return STATUS_ERROR
    try:
        app = _get_app()
        from firebase_admin import messaging
    except FcmNotConfigured as exc:
        logger.warning('FCM yapilandirilmamis, mobil bildirim atlandi: %s', exc)
        return STATUS_NOT_CONFIGURED
    except Exception as exc:
        logger.error('FCM baslatilamadi: %s', exc)
        return STATUS_NOT_CONFIGURED

    payload = {str(k): str(v) for k, v in (data or {}).items() if v is not None}
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body),
        data=payload,
        android=messaging.AndroidConfig(priority='high'),
        apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound='default'))),
    )
    try:
        message_id = messaging.send(message, dry_run=dry_run, app=app)
        logger.info('FCM bildirimi %s: %s (mesaj: %s)', 'dry-run basarili' if dry_run else 'iletildi', _short(token), message_id)
        return STATUS_SENT
    except (messaging.UnregisteredError, messaging.SenderIdMismatchError):
        logger.warning('FCM token gecersiz/suresi dolmus: %s', _short(token))
        return STATUS_UNREGISTERED
    except Exception as exc:
        logger.error('FCM gonderim hatasi (%s): %s', _short(token), type(exc).__name__)
        if admin_logger is not None:
            try:
                admin_logger.log_warning('FCM_SEND_ERROR', 'FCM gonderimi basarisiz: %s' % type(exc).__name__)
            except Exception:
                pass
        return STATUS_ERROR


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    parser = argparse.ArgumentParser(description='FCM test bildirimi gonder')
    parser.add_argument('--token', required=True, help='Cihaz FCM token')
    parser.add_argument('--title', default='MyTakip Test Bildirimi')
    parser.add_argument('--body', default='FCM yapilandirmasi basariyla calisiyor.')
    parser.add_argument('--dry-run', action='store_true', help='Gercek gonderim yapmadan dogrula')
    args = parser.parse_args()
    status = send_fcm_notification(args.token, args.title, args.body, {'screen': 'bills'}, dry_run=args.dry_run)
    print('Sonuc: %s' % status)
    sys.exit(0 if status == STATUS_SENT else 1)


if __name__ == '__main__':
    main()
