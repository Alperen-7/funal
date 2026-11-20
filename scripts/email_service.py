#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/email_service.py
========================================================================
Funal / MyTakip Birleşik E-Posta Gönderim Servisi (Unified Python Mailer)
========================================================================
Özellikler:
  1. Tek Merkezden Gönderim (Single Source of Truth):
     - 6 Haneli OTP E-Posta Doğrulama Kodları
     - Günlük Sabit Ödeme / Fatura Hatırlatmaları (send_reminders.py)
     - Admin Kritik Hata Uyarıları ve Saatlik Özet Raporları (admin_logger.py)
  2. Çift Sağlayıcı Desteği (EMAIL_PROVIDER):
     - 'smtp' (Varsayılan): Python yerleşik smtplib & email.mime (Gmail 465 SSL / 587 STARTTLS)
     - 'resend': Resend API (Özel doğrulanmış domain kullanımı için)
  3. Tam UTF-8 Türkçe Karakter Desteği (ğ, ü, ş, ı, ö, ç, İ, Ğ, Ü, Ş, Ö, Ç)
  4. Dinamik Gönderici Başlığı: SENDER_NAME <SENDER_EMAIL>
"""

import os
import re
import json
import time
import ssl
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, parseaddr

try:
    import requests
except ImportError:
    requests = None
    import urllib.request
    import urllib.error

try:
    import resend
except ImportError:
    resend = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [EmailService] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('EmailService')


def load_dotenv():
    """Proje kök dizinindeki .env dosyasını ortam değişkenlerine yükler."""
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
                            if k and (k not in os.environ or not os.environ[k]):
                                os.environ[k] = v
            except Exception:
                pass


load_dotenv()


def get_email_config():
    """Güncel ortam değişkenlerinden e-posta yapılandırmasını okur."""
    load_dotenv()
    provider = os.environ.get('EMAIL_PROVIDER', 'smtp').strip().lower() or 'smtp'
    raw_enabled = os.environ.get('EMAIL_ENABLED', 'false').strip().lower()
    email_enabled = raw_enabled in ('true', '1', 'yes', 'aktif', 'on') and provider not in ('disabled', 'passive', 'pasif', 'none', 'off')
    sender_name = os.environ.get('SENDER_NAME', 'Funal Bildirim').strip() or 'Funal Bildirim'
    raw_sender_email = os.environ.get('SENDER_EMAIL', '').strip()

    # Eğer SENDER_EMAIL içinde 'Ad <mail@domain.com>' formatı varsa ayrıştır
    parsed_name, parsed_addr = parseaddr(raw_sender_email)
    if parsed_addr and '@' in parsed_addr:
        sender_email = parsed_addr.strip()
        if parsed_name and not os.environ.get('SENDER_NAME'):
            sender_name = parsed_name.strip()
    else:
        sender_email = raw_sender_email

    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com').strip() or 'smtp.gmail.com'
    try:
        smtp_port = int(os.environ.get('SMTP_PORT', '465').strip())
    except ValueError:
        smtp_port = 465

    smtp_user = os.environ.get('SMTP_USER', '').strip() or sender_email
    # Google 16 haneli uygulama şifresindeki boşlukları temizle (örn: 'abcd efgh ijkl mnop' -> 'abcdefghijklmnop')
    raw_app_pw = os.environ.get('SMTP_APP_PASSWORD', '').strip()
    smtp_app_password = raw_app_pw.replace(' ', '')

    resend_api_key = os.environ.get('RESEND_API_KEY', '').strip()

    return {
        'enabled': email_enabled,
        'provider': provider,
        'sender_name': sender_name,
        'sender_email': sender_email,
        'formatted_from': f"{sender_name} <{sender_email}>" if sender_email else sender_name,
        'smtp_host': smtp_host,
        'smtp_port': smtp_port,
        'smtp_user': smtp_user,
        'smtp_app_password': smtp_app_password,
        'resend_api_key': resend_api_key
    }


def is_email_enabled():
    """E-posta gönderim modülünün aktif olup olmadığını döndürür."""
    return get_email_config()['enabled']


def get_formatted_sender():
    """'SENDER_NAME <SENDER_EMAIL>' formatında temiz gönderici bilgisini döndürür."""
    cfg = get_email_config()
    return cfg['formatted_from']


def validate_provider_credentials(provider=None):
    """
    Aktif e-posta sağlayıcısının (SMTP veya Resend) kimlik bilgilerinin
    tam olup olmadığını kontrol eder.
    Dönüş: (is_configured: bool, provider_name: str, diagnostic_msg: str)
    """
    cfg = get_email_config()
    active_provider = (provider or cfg['provider']).lower()

    if not cfg['enabled']:
        return False, 'pasif', "E-posta gönderimi pasif modda (EMAIL_ENABLED=false)"

    if not cfg['sender_email'] or '@' not in cfg['sender_email']:
        return False, active_provider, "SENDER_EMAIL tanımlanmamış veya geçersiz e-posta formatında."

    if active_provider == 'smtp':
        if not cfg['smtp_host']:
            return False, 'smtp', "SMTP_HOST tanımlanmamış."
        if not cfg['smtp_user']:
            return False, 'smtp', "SMTP_USER tanımlanmamış."
        if not cfg['smtp_app_password']:
            return False, 'smtp', "SMTP_APP_PASSWORD (16 haneli Google Uygulama Şifresi) tanımlanmamış."
        return True, 'smtp', f"SMTP hazır ({cfg['smtp_user']} @ {cfg['smtp_host']}:{cfg['smtp_port']})"

    elif active_provider == 'resend':
        if 'onboarding@resend.dev' in cfg['sender_email'].lower():
            logger.warning(
                "⚠️ [RESEND UYARISI]: SENDER_EMAIL olarak 'onboarding@resend.dev' seçili! "
                "Resend ücretsiz katmanında doğrulanmış özel alan adınız (custom domain) yoksa "
                "dış kullanıcı adreslerine gönderim reddedilir (403 Forbidden). "
                "Harici alıcılara gönderim için EMAIL_PROVIDER=smtp kullanın."
            )
        if not cfg['resend_api_key']:
            return False, 'resend', "RESEND_API_KEY tanımlanmamış."
        return True, 'resend', f"Resend API hazır ({cfg['formatted_from']})"

    return False, active_provider, f"Bilinmeyen EMAIL_PROVIDER değeri: '{active_provider}' ('smtp' veya 'resend' olmalı)"


def send_via_smtp(recipient_email, subject, html_body, cfg=None):
    """
    Python yerleşik smtplib ve email.mime kullanarak tam UTF-8 (Türkçe karakter)
    uyumlu HTML e-posta gönderir. Port 465 (SSL) ve Port 587 (STARTTLS) destekler.
    """
    cfg = cfg or get_email_config()
    sender_name = cfg['sender_name']
    sender_email = cfg['sender_email']
    smtp_host = cfg['smtp_host']
    smtp_port = cfg['smtp_port']
    smtp_user = cfg['smtp_user']
    smtp_password = cfg['smtp_app_password']

    if not sender_email or not smtp_user or not smtp_password:
        return False, (
            "SMTP kimlik bilgileri eksik (SENDER_EMAIL, SMTP_USER veya SMTP_APP_PASSWORD boş). "
            "Lütfen .env dosyanızı kontrol edin."
        )

    # MIMEMultipart ile UTF-8 kodlamalı mesaj oluştur
    msg = MIMEMultipart('alternative')
    msg.set_charset('utf-8')
    msg['Subject'] = Header(str(subject), 'utf-8')
    msg['From'] = formataddr((str(Header(sender_name, 'utf-8')), sender_email))
    msg['To'] = recipient_email

    html_part = MIMEText(str(html_body), 'html', 'utf-8')
    msg.attach(html_part)

    try:
        context = ssl.create_default_context()
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20, context=context) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(sender_email, [recipient_email], msg.as_bytes())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(sender_email, [recipient_email], msg.as_bytes())

        logger.info(f"✅ [SMTP] E-posta başarıyla gönderildi: {cfg['formatted_from']} -> {recipient_email}")
        return True, f"SMTP ile iletildi ({smtp_host}:{smtp_port})"

    except smtplib.SMTPAuthenticationError as auth_err:
        err_msg = (
            f"SMTP Kimlik Doğrulama Hatası (Kod {auth_err.smtp_code}): "
            f"Kullanıcı ({smtp_user}) veya SMTP_APP_PASSWORD reddedildi. "
            f"Gmail kullanıyorsanız normal hesap şifrenizi değil, Google Hesabı > Güvenlik > "
            f"2 Adımlı Doğrulama > Uygulama Şifreleri altından aldığınız 16 haneli şifreyi girdiğinizden emin olun."
        )
        logger.error(f"❌ {err_msg}")
        return False, err_msg
    except Exception as exc:
        err_msg = f"SMTP gönderim hatası ({smtp_host}:{smtp_port}): {exc}"
        logger.error(f"❌ {err_msg}")
        return False, err_msg


def send_via_resend(recipient_email, subject, html_body, cfg=None):
    """
    Resend API üzerinden e-posta gönderir.
    SENDER_EMAIL onboarding@resend.dev ise dış alıcı kısıtlaması hakkında net uyarı basar.
    """
    cfg = cfg or get_email_config()
    api_key = cfg['resend_api_key']
    formatted_from = cfg['formatted_from']

    if 'onboarding@resend.dev' in cfg['sender_email'].lower():
        logger.warning(
            "⚠️ [RESEND UYARISI]: SENDER_EMAIL olarak 'onboarding@resend.dev' kullanılıyor. "
            "Resend ücretsiz katmanı yalnızca kendi doğrulanmış geliştirici adresinize gönderime izin verir; "
            "dış kullanıcı adresleri reddedilecektir! Dış alıcılara gönderim için EMAIL_PROVIDER=smtp seçin."
        )

    if not api_key:
        return False, "RESEND_API_KEY tanımlı değil."

    try:
        if resend:
            resend.api_key = api_key
            res = resend.Emails.send({
                "from": formatted_from,
                "to": [recipient_email],
                "subject": subject,
                "html": html_body
            })
            email_id = res.get('id') if isinstance(res, dict) else getattr(res, 'id', str(res))
            logger.info(f"✅ [Resend] E-posta başarıyla gönderildi (ID: {email_id}): {formatted_from} -> {recipient_email}")
            return True, str(email_id)

        api_url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "from": formatted_from,
            "to": [recipient_email],
            "subject": subject,
            "html": html_body
        }
        if requests:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return True, data.get('id', 'ok')
        else:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode('utf-8'))
                return True, data.get('id', 'ok')

    except Exception as exc:
        err_msg = f"Resend API hatası: {exc}"
        logger.error(f"❌ {err_msg}")
        return False, err_msg


def send_email(recipient_email, subject, html_body, provider=None):
    """
    Tüm sistem için tek merkezli (unified) e-posta gönderim fonksiyonu.
    EMAIL_ENABLED=false olduğunda e-posta gönderimini güvenli biçimde pasife alır.
    """
    if not recipient_email or '@' not in str(recipient_email):
        return False, f"Geçersiz alıcı e-posta adresi: {recipient_email}"

    cfg = get_email_config()
    if not cfg['enabled'] and provider is None:
        logger.info(f"ℹ️ [E-Posta Pasif]: EMAIL_ENABLED=false olduğu için gönderim atlandı -> {recipient_email} ('{subject}')")
        return False, "E-posta gönderimi pasif modda (EMAIL_ENABLED=false)"

    active_provider = (provider or cfg['provider']).strip().lower()

    if active_provider == 'resend':
        return send_via_resend(recipient_email, subject, html_body, cfg=cfg)
    else:
        return send_via_smtp(recipient_email, subject, html_body, cfg=cfg)


def build_otp_email_html(otp_code, username=None):
    """6 haneli e-posta doğrulama kodu için Türkçe UTF-8 HTML şablonu üretir."""
    user_greeting = f"Merhaba <strong>{username}</strong>," if username else "Merhaba,"
    cfg = get_email_config()
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 520px; margin: 0 auto; background: #0f1117; color: #f1f5f9; border-radius: 16px; border: 1px solid #262b3d; overflow: hidden;">
      <div style="background: linear-gradient(135deg, #4f46e5, #0891b2); padding: 24px 28px;">
        <h2 style="margin: 0; font-size: 20px; color: #ffffff;">🔐 E-Posta Doğrulama Kodunuz</h2>
        <p style="margin: 6px 0 0; font-size: 13px; color: rgba(255,255,255,0.88);">{cfg['sender_name']} Güvenlik Doğrulaması</p>
      </div>
      <div style="padding: 28px;">
        <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1; margin-top: 0;">{user_greeting}</p>
        <p style="font-size: 14px; line-height: 1.6; color: #94a3b8;">
          Bildirim tercihlerinizi aktifleştirmek ve e-posta adresinizi doğrulamak için aşağıdaki <strong>6 haneli doğrulama kodunu</strong> uygulamaya girin:
        </p>
        <div style="background: #171b26; border: 1.5px dashed #6366f1; border-radius: 12px; padding: 18px; text-align: center; margin: 22px 0;">
          <span style="font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #38bdf8; font-family: monospace;">{otp_code}</span>
        </div>
        <p style="font-size: 12.5px; color: #64748b; text-align: center; margin-bottom: 0;">
          Bu kod 10 dakika boyunca geçerlidir. Eğer bu işlemi siz başlatmadıysanız bu e-postayı dikkate almayınız.
        </p>
      </div>
    </div>
    """


def send_otp_verification_email(recipient_email, otp_code, username=None):
    """6 haneli OTP doğrulama kodunu birleşik mailer üzerinden gönderir."""
    cfg = get_email_config()
    subject = f"🔐 [{cfg['sender_name']}] E-Posta Doğrulama Kodunuz: {otp_code}"
    html_body = build_otp_email_html(otp_code, username=username)
    return send_email(recipient_email, subject, html_body)
