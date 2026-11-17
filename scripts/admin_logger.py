#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/admin_logger.py
MyTakip Güvenli ve KVKK Uyumlu Admin Hata Loglama & Anlık Uyarı Modülü.

Özellikler:
  1. KVKK ve Hassas Veri Maskeleme (PIN, şifre, token, kart, api anahtarları asla açık basılmaz).
  2. Kritik Hatalarda (CRITICAL / ERROR) Resend API ile Admin'e anında e-posta uyarısı.
  3. Uyarı Seviyesindeki Hataların (WARNING) veritabanında (mt_error_logs) ve yerel günlükte biriktirilmesi.
  4. Spam Koruması (Debounce / Cooldown): Aynı kritik hata için 10 dakikada en fazla 1 e-posta atılır.
"""

import os
import sys
import json
import time
import re
import logging
import traceback
import warnings
from datetime import datetime, timezone

# macOS LibreSSL / urllib3 uyarılarını bastır
warnings.filterwarnings('ignore', message='.*urllib3 v2 only supports OpenSSL.*')
warnings.filterwarnings('ignore', category=UserWarning)

# .env dosyasından yükleme
def load_dotenv():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = [
        os.path.join(base_dir, '.env'),
        os.path.join(base_dir, '.env.local'),
        os.path.join(os.getcwd(), '.env'),
        os.path.join(os.getcwd(), '.env.local')
    ]
    for p in paths:
        if os.path.exists(p) and os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

load_dotenv()

# Logger yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [AdminLogger] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('AdminLogger')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_ANON_KEY', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'MyTakip Sistem <onboarding@resend.dev>')
ADMIN_EMAIL_ENV = os.environ.get('ADMIN_EMAIL', '')

try:
    import requests
except ImportError:
    requests = None
    import urllib.request
    import urllib.error
    import urllib.parse

try:
    import resend
    if RESEND_API_KEY:
        resend.api_key = RESEND_API_KEY
except ImportError:
    resend = None

# Son gönderilen kritik alert zaman damgaları (Debounce - spam engelleme)
_ALERT_COOLDOWN_SECONDS = 600  # 10 dakika
_LAST_ALERT_TIMESTAMPS = {}
_LOCAL_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'error_logs.jsonl')


# ── 1. KVKK & HASSAS VERİ MASKELEME ──
SENSITIVE_KEY_PATTERNS = re.compile(
    r'(pin|password|passwd|sifre|secret|token|apikey|api_key|authorization|auth|recovery|kurtarma|bearer|private_key|anon_key|service_role_key)',
    re.IGNORECASE
)

CREDIT_CARD_REGEX = re.compile(r'\b(?:\d[ -]*?){13,16}\b')
BEARER_REGEX = re.compile(r'Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', re.IGNORECASE)
PIN_ASSIGN_REGEX = re.compile(r'(pin|password|sifre|secret|token)\s*[:=]\s*[\'"]?([^\'",\s]+)[\'"]?', re.IGNORECASE)


def mask_sensitive_data(data):
    """
    KVKK ve güvenlik ilkeleri gereğince şifre, PIN, API anahtarı, kurtarma anahtarı,
    token ve kredi kartı numaralarını otomatik olarak maskeler.
    """
    if data is None:
        return data

    if isinstance(data, dict):
        masked_dict = {}
        for k, v in data.items():
            if SENSITIVE_KEY_PATTERNS.search(str(k)):
                masked_dict[k] = '***MASKED_SENSITIVE***'
            elif isinstance(v, (dict, list)):
                masked_dict[k] = mask_sensitive_data(v)
            elif isinstance(v, str):
                masked_dict[k] = mask_sensitive_text(v)
            else:
                masked_dict[k] = v
        return masked_dict

    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]

    if isinstance(data, str):
        return mask_sensitive_text(data)

    return data


def mask_sensitive_text(text):
    if not isinstance(text, str) or not text:
        return text

    # Kredi kartı maskeleme
    text = CREDIT_CARD_REGEX.sub('****-****-****-****', text)

    # Bearer token maskeleme
    text = BEARER_REGEX.sub('Bearer ***MASKED_TOKEN***', text)

    # PIN ve Parola atamalarını maskeleme (örn: pin: 123456 -> pin: ***MASKED***)
    text = PIN_ASSIGN_REGEX.sub(r'\1: ***MASKED***', text)

    # VAPID / Supabase anahtarları uzun hash maskeleme (eyJhbGciOi... vb.)
    text = re.sub(r'sb_publishable_[A-Za-z0-9_\-]+', 'sb_publishable_***MASKED***', text)
    text = re.sub(r're_[A-Za-z0-9_\-]+', 're_***MASKED***', text)

    return text


# ── 2. ADMİN E-POSTA ADRESİNİ BELİRLEME ──
def get_admin_email():
    """
    Öncelikle ADMIN_EMAIL ortam değişkenini kontrol eder;
    yoksa Supabase mt_users tablosunda is_admin=true veya role='admin' kullanıcısını sorgular.
    """
    if ADMIN_EMAIL_ENV and '@' in ADMIN_EMAIL_ENV:
        return ADMIN_EMAIL_ENV.strip()

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/mt_users"
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json'
            }
            # Admin kullanıcısını ara
            params = {'select': 'email,is_admin,role,username', 'order': 'created_at.asc'}
            if requests:
                r = requests.get(url, headers=headers, params=params, timeout=5)
                if r.status_code == 200:
                    rows = r.json()
                    for row in rows:
                        uname = (row.get('username') or '').lower()
                        is_adm = row.get('is_admin') or (row.get('role') == 'admin') or (uname == 'admin')
                        if is_adm and row.get('email'):
                            return row['email'].strip()
            else:
                full_url = f"{url}?{urllib.parse.urlencode(params)}"
                req = urllib.request.Request(full_url, headers=headers, method='GET')
                with urllib.request.urlopen(req, timeout=5) as resp:
                    rows = json.loads(resp.read().decode('utf-8'))
                    for row in rows:
                        uname = (row.get('username') or '').lower()
                        is_adm = row.get('is_admin') or (row.get('role') == 'admin') or (uname == 'admin')
                        if is_adm and row.get('email'):
                            return row['email'].strip()
        except Exception as e:
            logger.debug(f"Admin e-posta sorgusu yapılamadı: {e}")

    return 'admin@mytakip.local'


# ── 3. RESEND API İLE E-POSTA GÖNDERME ──
def send_resend_email(recipient_email, subject, html_content):
    if not RESEND_API_KEY:
        logger.warning(f"RESEND_API_KEY tanımlı değil. E-posta uyarısı atlandı: '{subject}' -> {recipient_email}")
        return False, "RESEND_API_KEY eksik"

    try:
        if resend:
            params = {
                "from": SENDER_EMAIL,
                "to": [recipient_email],
                "subject": subject,
                "html": html_content
            }
            res = resend.Emails.send(params)
            msg_id = res.get('id') if isinstance(res, dict) else getattr(res, 'id', str(res))
            logger.info(f"✓ Admin e-postası Resend üzerinden gönderildi: {recipient_email} (ID: {msg_id})")
            return True, msg_id
        else:
            api_url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
            body = {
                "from": SENDER_EMAIL,
                "to": [recipient_email],
                "subject": subject,
                "html": html_content
            }
            if requests:
                resp = requests.post(api_url, headers=headers, json=body, timeout=12)
                resp.raise_for_status()
                res = resp.json()
            else:
                req = urllib.request.Request(api_url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=12) as r:
                    res = json.loads(r.read().decode('utf-8'))

            msg_id = res.get('id', 'N/A')
            logger.info(f"✓ Admin e-postası Resend REST API ile gönderildi: {recipient_email} (ID: {msg_id})")
            return True, msg_id

    except Exception as exc:
        logger.error(f"❌ Resend API e-posta gönderim hatası: {exc}")
        return False, str(exc)


# ── 4. LOG KAYDINI VERİTABANINA VE DOSYAYA KAYDETME ──
def persist_error_log(level, category, message, details=None):
    masked_msg = mask_sensitive_text(str(message))
    masked_details = mask_sensitive_data(details or {})
    now_iso = datetime.now(timezone.utc).isoformat()

    record = {
        'level': level.upper(),
        'category': category.upper(),
        'message': masked_msg,
        'details': masked_details,
        'created_at': now_iso,
        'is_notified': (level.upper() == 'CRITICAL')
    }

    # 1. Supabase mt_error_logs tablosuna yazma (immutable append)
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/mt_error_logs"
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
            }
            if requests:
                requests.post(url, headers=headers, json=[record], timeout=5)
            else:
                req = urllib.request.Request(url, data=json.dumps([record]).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=5):
                    pass
        except Exception:
            # Tablo henüz Supabase üzerinde oluşturulmamışsa veya bağlantı yoksa sessizce yerel dosyaya geç
            pass

    # 2. Yerel JSONL log dosyasına immutable ekleme (Local audit fallback)
    try:
        with open(_LOCAL_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception:
        pass


# ── 5. KRİTİK HATA ANLIK BİLDİRİMİ (IMMEDIATE ALERTS) ──
def log_critical(category, message, exc=None, context=None):
    """
    Prod ortamını etkileyen kritik hatalar (DB bağlantı kopması, 500 hatası, API çökmesi).
    Konsola yazar, mt_error_logs'a kaydeder ve Admin'e anında e-posta atar.
    """
    masked_msg = mask_sensitive_text(str(message))
    tb_str = ""
    if exc is not None:
        tb_str = mask_sensitive_text(traceback.format_exc() if traceback.format_exc().strip() != "NoneType: None" else str(exc))

    logger.critical(f"🚨 [{category}] {masked_msg}")

    details = context or {}
    if tb_str:
        details['traceback'] = tb_str

    persist_error_log('CRITICAL', category, masked_msg, details)

    # Debounce kontrolü: aynı kategorideki hata son 10 dakikada iletildiyse e-posta spamı yapma
    now = time.time()
    last_sent = _LAST_ALERT_TIMESTAMPS.get(category, 0)
    if (now - last_sent) < _ALERT_COOLDOWN_SECONDS:
        logger.info(f"⏳ [{category}] için son 10 dakika içinde kritik alert iletildi. E-posta spamı engellendi (cooldown aktif).")
        return False, "Cooldown aktif"

    _LAST_ALERT_TIMESTAMPS[category] = now

    admin_email = get_admin_email()
    subject = f"🚨 [KRİTİK HATA] MyTakip Sistem Uyarısı: {category}"
    time_str = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
      <meta charset="UTF-8">
      <title>Kritik Sistem Uyarısı</title>
      <style>
        body {{ margin:0; padding:0; background:#080b12; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color:#f8fafc; }}
        .wrap {{ max-width:620px; margin:24px auto; background:#0f1422; border:1px solid rgba(239,68,68,0.3); border-radius:14px; overflow:hidden; }}
        .hdr {{ background:linear-gradient(135deg, #b91c1c, #ef4444); padding:20px 24px; text-align:center; }}
        .hdr h1 {{ margin:0; font-size:20px; color:#ffffff; font-weight:800; }}
        .body {{ padding:24px 28px; }}
        .badge {{ display:inline-block; background:rgba(239,68,68,0.2); border:1px solid #ef4444; color:#fca5a5; padding:5px 12px; border-radius:9999px; font-size:12px; font-weight:700; margin-bottom:16px; }}
        .card {{ background:#161c2e; border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:16px; margin:14px 0; }}
        .code {{ background:#05070d; border:1px solid rgba(255,255,255,0.06); padding:12px; border-radius:8px; font-family:monospace; font-size:12px; color:#f87171; overflow-x:auto; white-space:pre-wrap; }}
        .footer {{ text-align:center; padding:16px 24px; font-size:12px; color:#64748b; border-top:1px solid rgba(255,255,255,0.06); }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="hdr">
          <h1>🚨 MyTakip Kritik Sistem Uyarısı</h1>
        </div>
        <div class="body">
          <div style="text-align:center;">
            <span class="badge">CRITICAL ALERT · PROD ETKİSİ</span>
          </div>
          <p style="font-size:14px; color:#cbd5e1; line-height:1.6;">
            Sisteminizde anında müdahale gerektiren kritik bir hata yakalandı. Detaylar KVKK ve güvenlik standartlarına göre maskelenerek aşağıda özetlenmiştir:
          </p>
          <div class="card">
            <div style="margin-bottom:8px; font-size:13px;"><strong>Hata Kategorisi:</strong> <span style="color:#f87171; font-weight:700;">{category}</span></div>
            <div style="margin-bottom:8px; font-size:13px;"><strong>Zaman:</strong> {time_str}</div>
            <div style="margin-bottom:8px; font-size:13px;"><strong>Hata Mesajı:</strong> {masked_msg}</div>
          </div>
          {f'<div class="card"><strong style="font-size:12.5px; color:#94a3b8; display:block; margin-bottom:6px;">Teknik Hata İzi (Traceback - Maskelenmiş):</strong><div class="code">{tb_str}</div></div>' if tb_str else ''}
          <p style="font-size:12.5px; color:#94a3b8; margin-top:16px;">
            ℹ️ Bu e-posta, sistem kararlılığı için Resend API ve MyTakip Admin Logger aracılığıyla anında otomatik iletilmiştir.
          </p>
        </div>
        <div class="footer">
          MyTakip Otomatik İzleme ve Hata Bildirim Motoru
        </div>
      </div>
    </body>
    </html>
    """

    return send_resend_email(admin_email, subject, html_content)


# ── 6. UYARI SEVİYESİNDEKİ HATALARI BİRİKTİRME (HOURLY LOGGING) ──
def log_warning(category, message, exc=None, context=None):
    """
    Warning (uyarı) seviyesindeki geçici hatalar (rate limit, timeout, başarısız giriş denemesi).
    Konsola yazar ve saatlik özet için mt_error_logs tablosuna / error_logs.jsonl dosyasına kaydeder.
    """
    masked_msg = mask_sensitive_text(str(message))
    tb_str = ""
    if exc is not None:
        tb_str = mask_sensitive_text(str(exc))

    logger.warning(f"⚠️ [{category}] {masked_msg}")

    details = context or {}
    if tb_str:
        details['error'] = tb_str

    persist_error_log('WARNING', category, masked_msg, details)
    return True
