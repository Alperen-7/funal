#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mobile_api.py
Capacitor (Android/iOS) istemcileri icin backend yardimcilari:

  * CORS izin listesi (capacitor://localhost, http(s)://localhost, GitHub Pages ...)
  * Cerez yerine Authorization: Bearer <token> (HS256 imzali, stdlib ile)
  * POST /api/auth/token      -> kullanici adi + pin_hash dogrulanir, kisa omurlu token doner
  * POST /api/push/register   -> FCM token'i mt_push_subscriptions tablosuna yazar
  * DELETE /api/push/register -> FCM token'i pasife alir (kayit silinmez, is_active=false)

Yalnizca standart kutuphane kullanir (server.py ile ayni kisit).
Gerekli ortam degiskenleri: API_TOKEN_SECRET (en az 32 karakter), SUPABASE_URL,
SUPABASE_SERVICE_ROLE_KEY. Eksikse ilgili endpoint'ler kapali (fail closed) davranir.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

try:
    import scripts.admin_logger as admin_logger
except ImportError:
    try:
        import admin_logger
    except ImportError:
        admin_logger = None

logger = logging.getLogger('MobileApi')

TOKEN_ISSUER = 'mytakip'
DEFAULT_TOKEN_TTL_SECONDS = 24 * 3600
MIN_SECRET_LENGTH = 32
MAX_BODY_BYTES = 8192

RATE_LIMIT_MAX_FAILURES = 5
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_KEYS = 10000

BUILTIN_ORIGINS = frozenset({
    'capacitor://localhost',
    'ionic://localhost',
    'http://localhost',
    'https://localhost',
})
DEFAULT_WEB_APP_URL = 'https://alperen-7.github.io/funal'

CORS_ALLOW_METHODS = 'GET, POST, DELETE, OPTIONS'
CORS_ALLOW_HEADERS = 'Content-Type, Authorization, Pragma, Cache-Control'

USERNAME_RE = re.compile(r'^[\w.\-]{1,64}$')
FCM_TOKEN_RE = re.compile(r'^[A-Za-z0-9_\-:.]{100,4096}$')
APNS_HEX_TOKEN_RE = re.compile(r'^[0-9a-fA-F]{64}$')
PUSH_PLATFORMS = frozenset({'android', 'ios'})

AUTH_TOKEN_PATH = '/api/auth/token'
PUSH_REGISTER_PATH = '/api/push/register'
MOBILE_PATHS = frozenset({AUTH_TOKEN_PATH, PUSH_REGISTER_PATH})


class BackendNotConfigured(Exception):
    pass


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _origin_of(url):
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return '%s://%s' % (parsed.scheme, parsed.netloc)


def allowed_origins():
    origins = set(BUILTIN_ORIGINS)
    web_origin = _origin_of(os.environ.get('APP_URL', DEFAULT_WEB_APP_URL))
    if web_origin:
        origins.add(web_origin)
    for extra in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(','):
        extra = extra.strip().rstrip('/')
        if extra:
            origins.add(extra)
    return origins


def resolve_cors_origin(origin):
    if not origin:
        return None
    origin = origin.strip().rstrip('/')
    if origin in allowed_origins():
        return origin
    try:
        parsed = urllib.parse.urlparse(origin)
    except ValueError:
        return None
    if parsed.scheme in ('http', 'https') and parsed.hostname in ('localhost', '127.0.0.1'):
        return origin
    return None


def cors_headers(origin):
    headers = [('Vary', 'Origin')]
    allowed = resolve_cors_origin(origin)
    if allowed:
        headers.extend([
            ('Access-Control-Allow-Origin', allowed),
            ('Access-Control-Allow-Methods', CORS_ALLOW_METHODS),
            ('Access-Control-Allow-Headers', CORS_ALLOW_HEADERS),
            ('Access-Control-Max-Age', '600'),
        ])
    return headers


def _b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _b64url_decode(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _token_secret():
    secret = os.environ.get('API_TOKEN_SECRET', '')
    if len(secret) < MIN_SECRET_LENGTH:
        return None
    return secret.encode('utf-8')


def token_ttl_seconds():
    try:
        ttl = int(os.environ.get('API_TOKEN_TTL_SECONDS', DEFAULT_TOKEN_TTL_SECONDS))
    except ValueError:
        return DEFAULT_TOKEN_TTL_SECONDS
    return max(60, min(ttl, 7 * 24 * 3600))


def _sign(signing_input, secret):
    return _b64url_encode(hmac.new(secret, signing_input.encode('ascii'), hashlib.sha256).digest())


def issue_token(username, now=None):
    secret = _token_secret()
    if secret is None:
        raise BackendNotConfigured('API_TOKEN_SECRET tanimli degil veya cok kisa')
    issued_at = int(now if now is not None else time.time())
    header = _b64url_encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode('utf-8'))
    claims = _b64url_encode(json.dumps({
        'iss': TOKEN_ISSUER,
        'sub': username,
        'iat': issued_at,
        'exp': issued_at + token_ttl_seconds(),
    }, separators=(',', ':')).encode('utf-8'))
    signing_input = '%s.%s' % (header, claims)
    return '%s.%s' % (signing_input, _sign(signing_input, secret))


def verify_token(token, now=None) -> Optional[str]:
    secret = _token_secret()
    if secret is None or not isinstance(token, str):
        return None
    parts = token.split('.')
    if len(parts) != 3:
        return None
    signing_input = '%s.%s' % (parts[0], parts[1])
    if not hmac.compare_digest(_sign(signing_input, secret), parts[2]):
        return None
    try:
        header = json.loads(_b64url_decode(parts[0]))
        claims = json.loads(_b64url_decode(parts[1]))
    except (ValueError, TypeError):
        return None
    if header.get('alg') != 'HS256' or claims.get('iss') != TOKEN_ISSUER:
        return None
    current = now if now is not None else time.time()
    exp = claims.get('exp')
    if not isinstance(exp, (int, float)) or exp <= current:
        return None
    subject = claims.get('sub')
    if not isinstance(subject, str) or not USERNAME_RE.match(subject):
        return None
    return subject


_failures_lock = threading.Lock()
_failures = {}


def _prune_failures(now):
    if len(_failures) < RATE_LIMIT_MAX_KEYS:
        return
    for key in [k for k, stamps in _failures.items() if not [t for t in stamps if now - t < RATE_LIMIT_WINDOW_SECONDS]]:
        _failures.pop(key, None)
    if len(_failures) >= RATE_LIMIT_MAX_KEYS:
        _failures.clear()


def _is_rate_limited(key, now=None):
    now = now if now is not None else time.time()
    with _failures_lock:
        recent = [t for t in _failures.get(key, []) if now - t < RATE_LIMIT_WINDOW_SECONDS]
        _failures[key] = recent
        return len(recent) >= RATE_LIMIT_MAX_FAILURES


def _record_failure(key, now=None):
    now = now if now is not None else time.time()
    with _failures_lock:
        _prune_failures(now)
        _failures.setdefault(key, []).append(now)


def _clear_failures(key):
    with _failures_lock:
        _failures.pop(key, None)


def reset_rate_limits():
    with _failures_lock:
        _failures.clear()


def _supabase_request(method, path_and_query, payload=None, prefer=None):
    base_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not base_url or not service_key:
        raise BackendNotConfigured('SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY tanimli degil')
    headers = {
        'apikey': service_key,
        'Authorization': 'Bearer ' + service_key,
        'Content-Type': 'application/json',
    }
    if prefer:
        headers['Prefer'] = prefer
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    request = urllib.request.Request(base_url + '/rest/v1/' + path_and_query, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read()
    return json.loads(raw.decode('utf-8')) if raw else None


def _clean_username(value):
    if not isinstance(value, str):
        return None
    username = value.strip().lower()
    return username if USERNAME_RE.match(username) else None


def verify_credentials(username, pin_hash):
    query = 'mt_users?username=eq.%s&select=pin_hash&limit=1' % urllib.parse.quote(username, safe='')
    rows = _supabase_request('GET', query)
    stored = str(rows[0].get('pin_hash') or '') if rows else ''
    matches = hmac.compare_digest(stored.encode('utf-8'), pin_hash.encode('utf-8'))
    return bool(stored) and matches


def _log_auth_failure(username):
    if admin_logger is not None:
        try:
            admin_logger.log_warning('AUTH_FAILURE', 'Mobil API token istegi basarisiz: kullanici=%s' % username)
        except Exception:
            pass


def handle_auth_token(body):
    username = _clean_username(body.get('username'))
    pin_hash = body.get('pin_hash')
    if not username or not isinstance(pin_hash, str) or not 1 <= len(pin_hash) <= 256:
        return 400, {'error': 'Gecersiz istek'}
    if _token_secret() is None:
        return 503, {'error': 'Sunucu kimlik dogrulamasi yapilandirilmamis'}
    if _is_rate_limited(username):
        return 429, {'error': 'Cok fazla basarisiz deneme. Biraz sonra tekrar deneyin.'}
    try:
        valid = verify_credentials(username, pin_hash)
    except BackendNotConfigured:
        return 503, {'error': 'Sunucu veritabani yapilandirilmamis'}
    except Exception as exc:
        logger.error('Kimlik dogrulama servisi hatasi: %s', exc)
        return 502, {'error': 'Kimlik dogrulama servisine ulasilamadi'}
    if not valid:
        _record_failure(username)
        _log_auth_failure(username)
        return 401, {'error': 'Kimlik dogrulama basarisiz'}
    _clear_failures(username)
    return 200, {
        'token': issue_token(username),
        'token_type': 'Bearer',
        'expires_in': token_ttl_seconds(),
    }


def _authenticate(authorization):
    if _token_secret() is None:
        raise ApiError(503, 'Sunucu kimlik dogrulamasi yapilandirilmamis')
    if not isinstance(authorization, str) or not authorization.startswith('Bearer '):
        raise ApiError(401, 'Authorization: Bearer <token> gerekli')
    username = verify_token(authorization[len('Bearer '):].strip())
    if not username:
        raise ApiError(401, 'Token gecersiz veya suresi dolmus')
    return username


def _validate_fcm_token(token):
    if not isinstance(token, str):
        raise ApiError(400, 'fcm_token gerekli')
    token = token.strip()
    if APNS_HEX_TOKEN_RE.match(token):
        raise ApiError(400, 'Bu bir ham APNs token. FCM token gerekli (iOS Firebase kurulumunu kontrol edin).')
    if not FCM_TOKEN_RE.match(token):
        raise ApiError(400, 'fcm_token formati gecersiz')
    return token


def handle_push_register(authorization, body):
    try:
        username = _authenticate(authorization)
        token = _validate_fcm_token(body.get('fcm_token'))
        platform = body.get('platform')
        if platform not in PUSH_PLATFORMS:
            raise ApiError(400, 'platform android veya ios olmali')
        row = {
            'username': username,
            'endpoint': 'fcm:' + token,
            'fcm_token': token,
            'platform': platform,
            'is_active': True,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        _supabase_request(
            'POST',
            'mt_push_subscriptions?on_conflict=endpoint',
            [row],
            prefer='resolution=merge-duplicates,return=minimal',
        )
    except ApiError as err:
        return err.status, {'error': err.message}
    except BackendNotConfigured:
        return 503, {'error': 'Sunucu veritabani yapilandirilmamis'}
    except Exception as exc:
        logger.error('Push kaydi hatasi: %s', exc)
        return 502, {'error': 'Push kaydi veritabanina yazilamadi'}
    return 200, {'ok': True}


def handle_push_unregister(authorization, body):
    try:
        username = _authenticate(authorization)
        token = _validate_fcm_token(body.get('fcm_token'))
        query = 'mt_push_subscriptions?fcm_token=eq.%s&username=eq.%s' % (
            urllib.parse.quote(token, safe=''),
            urllib.parse.quote(username, safe=''),
        )
        _supabase_request(
            'PATCH',
            query,
            {'is_active': False, 'updated_at': datetime.now(timezone.utc).isoformat()},
            prefer='return=minimal',
        )
    except ApiError as err:
        return err.status, {'error': err.message}
    except BackendNotConfigured:
        return 503, {'error': 'Sunucu veritabani yapilandirilmamis'}
    except Exception as exc:
        logger.error('Push kaydi pasife alma hatasi: %s', exc)
        return 502, {'error': 'Push kaydi guncellenemedi'}
    return 200, {'ok': True}


def is_mobile_path(path):
    return path in MOBILE_PATHS


def dispatch(method, path, headers, body_bytes):
    if not is_mobile_path(path):
        return None
    method = (method or '').upper()
    allowed = {'POST'} if path == AUTH_TOKEN_PATH else {'POST', 'DELETE'}
    if method not in allowed:
        return 405, {'error': 'Method not allowed'}
    if body_bytes is None:
        body_bytes = b''
    if len(body_bytes) > MAX_BODY_BYTES:
        return 413, {'error': 'Istek govdesi cok buyuk'}
    try:
        body = json.loads(body_bytes.decode('utf-8')) if body_bytes else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {'error': 'Gecersiz JSON'}
    if not isinstance(body, dict):
        return 400, {'error': 'JSON nesnesi bekleniyor'}
    if path == AUTH_TOKEN_PATH:
        return handle_auth_token(body)
    authorization = headers.get('Authorization') if headers is not None else None
    if method == 'DELETE':
        return handle_push_unregister(authorization, body)
    return handle_push_register(authorization, body)
