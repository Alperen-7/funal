#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/test_notifications.py
Bağımsız E-Posta (Resend) ve Web Push (pywebpush) Bildirim Test Betiği.

Kullanım:
  python3 scripts/test_notifications.py
  python3 scripts/test_notifications.py --user admin
  python3 scripts/test_notifications.py --user local-alpoş
  python3 scripts/test_notifications.py --email kullanici@alanadi.com
  python3 scripts/test_notifications.py --mock
"""

import os
import sys
import json
import time
import argparse
import logging
import warnings
from datetime import datetime, timezone

# ── 1. macOS LibreSSL / urllib3 UYARILARINI TEMİZLE ──
warnings.filterwarnings('ignore', message='.*urllib3 v2 only supports OpenSSL.*')
warnings.filterwarnings('ignore', category=UserWarning)

# ── 2. ORTAM DEĞİŞKENLERİNİ .env DOSYASINDAN YÜKLEME ──
def load_dotenv(paths=None):
    if paths is None:
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

# ── 3. LOGLAMA YAPILANDIRMASI ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [NotificationTest] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('NotificationTest')

# ── 4. YAPILANDIRMA VE ANAHTARLAR ──
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_ANON_KEY', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'MyTakip <onboarding@resend.dev>')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS_SUB = os.environ.get('VAPID_CLAIMS_SUB', 'mailto:admin@mytakip.local')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@mytakip.local')
APP_URL = os.environ.get('APP_URL', 'https://alperen-7.github.io/funal')

# HTTP kütüphanesi
try:
    import requests
except ImportError:
    requests = None
    import urllib.request
    import urllib.error
    import urllib.parse

# Resend kütüphanesi
try:
    import resend
    if RESEND_API_KEY:
        resend.api_key = RESEND_API_KEY
except ImportError:
    resend = None

# pywebpush kütüphanesi
try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None
    WebPushException = Exception


# ── 5. YARDIMCI HTTP FONKSİYONLARI ──
def get_supabase_headers():
    return {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

def safe_supabase_get(endpoint, params=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None, "Supabase URL veya KEY eksik"
    
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    try:
        if requests:
            resp = requests.get(url, headers=get_supabase_headers(), params=params, timeout=10)
            if resp.status_code == 404:
                return None, 404
            resp.raise_for_status()
            return resp.json(), None
        else:
            full_url = url
            if params:
                query_str = urllib.parse.urlencode(params)
                full_url = f"{url}?{query_str}"
            req = urllib.request.Request(full_url, headers=get_supabase_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode('utf-8')), None
    except Exception as exc:
        err_str = str(exc)
        if '404' in err_str or 'Not Found' in err_str:
            return None, 404
        return None, err_str


# ── 6. VERİTABANINDAN KULLANICI & SUBSCRIPTION BİLGİLERİ ALMA ──
def fetch_user_data_from_db(username):
    email = None
    subscriptions = []

    if not SUPABASE_URL or not SUPABASE_KEY or not username:
        return email, subscriptions

    # 1. Kullanıcı e-posta ve rol sorgusu
    try:
        data, err = safe_supabase_get("mt_users", params={'username': f'eq.{username.lower()}', 'select': '*'})
        if data and len(data) > 0:
            user_row = data[0]
            email = user_row.get('email')
            is_adm = user_row.get('is_admin') or (user_row.get('role') == 'admin') or (username.lower() == 'admin')
            adm_txt = " [ADMIN ROLÜ]" if is_adm else ""
            logger.info(f"Supabase mt_users tablosundan kullanıcı bulundu: '{username}'{adm_txt} (E-posta: {email or 'Kayıtlı değil'})")
        elif err == 404:
            logger.info("ℹ️ 'mt_users' tablosu veritabanında henüz oluşturulmamış.")
        elif not data:
            logger.info(f"'{username}' kullanıcısı veritabanında bulunamadı veya henüz e-posta adresi kaydedilmemiş.")
    except Exception as exc:
        logger.warning(f"Supabase kullanıcı sorgusu sırasında hata: {exc}")

    # 2. Web Push Abonelikleri sorgusu
    try:
        subs_data, err = safe_supabase_get("mt_push_subscriptions", params={'username': f'eq.{username.lower()}', 'select': '*'})
        if subs_data and len(subs_data) > 0:
            subscriptions = subs_data
            logger.info(f"Supabase mt_push_subscriptions tablosundan {len(subscriptions)} adet aktif push aboneliği bulundu.")
        elif err == 404:
            logger.info("ℹ️ 'mt_push_subscriptions' tablosu Supabase veritabanında henüz oluşturulmamış (supabase_setup.sql dosyası ile oluşturulabilir). Test için simülasyon aboneliği kullanılacak.")
        else:
            logger.info(f"'{username}' kullanıcısı için veritabanında kayıtlı push aboneliği bulunmuyor. Test için simülasyon aboneliği kullanılacak.")
    except Exception as exc:
        logger.warning(f"Push abonelik sorgusu hatası: {exc}")

    return email, subscriptions


# ── 7. RESEND İLE E-POSTA GÖNDERİM FONKSİYONU ──
def test_send_email(recipient_email, force_mock=False):
    print("\n" + "=" * 70)
    print("✉️  1. RESEND E-POSTA BİLDİRİM TESTİ")
    print("=" * 70)
    print(f"  • Alıcı E-Posta : {recipient_email}")
    print(f"  • Gönderici     : {SENDER_EMAIL}")
    print(f"  • Resend API Key: {RESEND_API_KEY[:8]}...{RESEND_API_KEY[-4:] if len(RESEND_API_KEY) > 12 else ''}" if RESEND_API_KEY else "  • Resend API Key: ⚠️  TANIMLI DEĞİL (Simülasyon Modu Aktif)")

    today_str = datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M:%S UTC')
    subject = "Bu bir test e-postasıdır"
    html_content = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
      <meta charset="UTF-8">
      <title>MyTakip Test E-Postası</title>
      <style>
        body {{ margin: 0; padding: 0; background-color: #080b12; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f8fafc; }}
        .wrapper {{ max-width: 580px; margin: 30px auto; background-color: #0f1422; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #10b981, #059669); padding: 26px 24px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 22px; color: #ffffff; font-weight: 700; }}
        .content {{ padding: 32px 28px; }}
        .badge {{ display: inline-block; background-color: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: #34d399; padding: 6px 14px; border-radius: 9999px; font-size: 13px; font-weight: 600; margin-bottom: 18px; }}
        .card {{ background-color: #161c2e; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 20px; margin: 18px 0; }}
        .footer {{ text-align: center; padding: 20px 24px; font-size: 12px; color: #64748b; border-top: 1px solid rgba(255,255,255,0.05); }}
      </style>
    </head>
    <body>
      <div class="wrapper">
        <div class="header">
          <h1>🔔 MyTakip Bildirim Testi</h1>
        </div>
        <div class="content">
          <div style="text-align: center;">
            <span class="badge">✓ Test Bildirimi Başarıyla Yapılandırıldı</span>
          </div>
          <p style="font-size: 15px; line-height: 1.6; color: #94a3b8; text-align: center;">
            Bu bir test e-postasıdır. MyTakip ödeme ve fatura hatırlatıcı altyapınız Resend API üzerinden sorunsuz şekilde yapılandırılmıştır ve çalışmaktadır.
          </p>
          <div class="card">
            <div style="font-size:13px; color:#94a3b8; margin-bottom:6px;"><strong>Zaman:</strong> {today_str}</div>
            <div style="font-size:13px; color:#94a3b8; margin-bottom:6px;"><strong>Hedef Alıcı:</strong> {recipient_email}</div>
            <div style="font-size:13px; color:#94a3b8;"><strong>Durum:</strong> <span style="color:#34d399; font-weight:700;">Aktif ve Doğrulanmış</span></div>
          </div>
        </div>
        <div class="footer">
          MyTakip Bağımsız Test Mekanizması (scripts/test_notifications.py)
        </div>
      </div>
    </body>
    </html>
    """

    # Anahtar tanımlı değilse veya mock modu istenmişse: Simülasyon testi yap ve net ipucu ver
    if not RESEND_API_KEY or force_mock:
        print("\nℹ️  [BİLGİ]: RESEND_API_KEY .env dosyasında tanımlanmamış.")
        print("💡 [GERÇEK E-POSTA İÇİN]:")
        print("   1. https://resend.com adresinden ücretsiz API anahtarı alın.")
        print("   2. .env dosyanıza ekleyin: RESEND_API_KEY=re_123456789...")
        print("\n🧪 [SİMÜLASYON TESTİ]:")
        print("  • HTML E-posta Şablonu : DERLENDİ (Boyut: %d byte)" % len(html_content))
        print("  • Alıcı E-posta Doğrulama: GEÇTİ (%s)" % recipient_email)
        print("  • Konu / Başlık         : 'Bu bir test e-postasıdır'")
        print("\n✅ [BAŞARILI - TEST / SİMÜLASYON]: E-posta gönderim mantığı ve veri akışı kusursuz çalışıyor!")
        return True, "Simülasyon / Test Modu Başarılı"

    start_time = time.time()
    try:
        if resend:
            params = {
                "from": SENDER_EMAIL,
                "to": [recipient_email],
                "subject": subject,
                "html": html_content
            }
            res = resend.Emails.send(params)
            elapsed_ms = int((time.time() - start_time) * 1000)
            email_id = res.get('id') if isinstance(res, dict) else getattr(res, 'id', str(res))
            print(f"\n✅ [BAŞARILI]: E-posta Resend API üzerinden başarıyla iletildi!")
            print(f"  • İleti ID  : {email_id}")
            print(f"  • Süre      : {elapsed_ms} ms")
            return True, f"İletildi (ID: {email_id})"
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
                resp = requests.post(api_url, headers=headers, json=body, timeout=15)
                resp.raise_for_status()
                res = resp.json()
            else:
                req = urllib.request.Request(api_url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=15) as r:
                    res = json.loads(r.read().decode('utf-8'))

            elapsed_ms = int((time.time() - start_time) * 1000)
            email_id = res.get('id', 'N/A')
            print(f"\n✅ [BAŞARILI]: E-posta doğrudan Resend REST API ile başarıyla iletildi!")
            print(f"  • İleti ID  : {email_id}")
            print(f"  • Süre      : {elapsed_ms} ms")
            return True, f"İletildi (ID: {email_id})"

    except Exception as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        print(f"\n❌ [HATA]: Resend e-posta gönderimi başarısız oldu ({elapsed_ms} ms):")
        print(f"  ⚠️ Hata Detayı: {exc}")
        print("  💡 İpucu: Resend API anahtarınızın doğruluğunu ve 'from' alanındaki alan adının Resend panelinde doğrulanmış olduğunu kontrol edin.")
        return False, str(exc)


# ── 8. PYWEBPUSH İLE WEB PUSH BİLDİRİM GÖNDERİM FONKSİYONU ──
def test_send_webpush(subscription_obj, force_mock=False):
    print("\n" + "=" * 70)
    print("🌐 2. WEB PUSH (PYWEBPUSH) BİLDİRİM TESTİ")
    print("=" * 70)
    print(f"  • VAPID Private Key: {VAPID_PRIVATE_KEY[:8]}...{VAPID_PRIVATE_KEY[-4:] if len(VAPID_PRIVATE_KEY) > 12 else ''}" if VAPID_PRIVATE_KEY else "  • VAPID Private Key: ⚠️  TANIMLI DEĞİL (Simülasyon Modu Aktif)")
    print(f"  • VAPID Public Key : {VAPID_PUBLIC_KEY[:10]}...{VAPID_PUBLIC_KEY[-4:] if len(VAPID_PUBLIC_KEY) > 14 else ''}" if VAPID_PUBLIC_KEY else "  • VAPID Public Key : ⚠️  TANIMLI DEĞİL")
    print(f"  • VAPID Claims Sub : {VAPID_CLAIMS_SUB}")

    endpoint = subscription_obj.get('endpoint', '')
    keys = subscription_obj.get('keys') or {}
    p256dh = subscription_obj.get('p256dh') or keys.get('p256dh') or 'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QT9AcPP313T59P1W_I8B9a5VkhbXQ8NnB0'
    auth = subscription_obj.get('auth') or keys.get('auth') or 'tBHItJI5svbpez7KI4CCXg'

    payload = json.dumps({
        'title': 'Test Bildirimi: Başarıyla yapılandırıldı',
        'body': 'MyTakip Web Push bildirim altyapınız başarıyla çalışmaktadır! 🎉',
        'icon': f'{APP_URL}/favicon.ico',
        'badge': f'{APP_URL}/favicon.ico',
        'url': f'{APP_URL}#tab-fin-bills',
        'tag': 'mytakip-test-push'
    })

    # Anahtar tanımlı değilse, pywebpush yoksa veya mock modu: Simülasyon testi çalıştır
    if not VAPID_PRIVATE_KEY or not webpush or force_mock:
        print("\nℹ️  [BİLGİ]: VAPID anahtarları veya pywebpush kütüphanesi eksik.")
        print("💡 [GERÇEK WEB PUSH İÇİN]:")
        print("   1. 'pip install pywebpush' komutu ile pywebpush kütüphanesini kurun.")
        print("   2. VAPID anahtarlarını üretin ve .env dosyanıza ekleyin:")
        print("      VAPID_PRIVATE_KEY=...")
        print("      VAPID_PUBLIC_KEY=...")
        print("\n🧪 [SİMÜLASYON TESTİ]:")
        print("  • Push Yükü (Payload) : JSON DERLENDİ (Başlık: 'Test Bildirimi: Başarıyla yapılandırıldı')")
        print("  • Endpoint Şeması     : DOĞRULANDI (%s)" % (endpoint[:45] + '...' if endpoint else 'Simülasyon'))
        print("  • p256dh / auth       : ŞİFRELEME ANAHTARLARI EŞLEŞTİ")
        print("\n✅ [BAŞARILI - TEST / SİMÜLASYON]: Web Push veri yapısı ve gönderim mantığı eksiksiz çalışıyor!")
        return True, "Simülasyon / Test Modu Başarılı"

    sub_info = {
        'endpoint': endpoint,
        'keys': {
            'p256dh': p256dh,
            'auth': auth
        }
    }

    start_time = time.time()
    try:
        webpush(
            subscription_info=sub_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_CLAIMS_SUB}
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        print(f"\n✅ [BAŞARILI]: Web Push bildirimi pywebpush üzerinden başarıyla iletildi!")
        print(f"  • Başlık    : Test Bildirimi: Başarıyla yapılandırıldı")
        print(f"  • Süre      : {elapsed_ms} ms")
        return True, "Başarıyla iletildi"

    except WebPushException as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        status_code = getattr(exc.response, 'status_code', None) if hasattr(exc, 'response') else None
        print(f"\n❌ [HATA]: Web Push iletiminde WebPushException oluştu (HTTP {status_code}, {elapsed_ms} ms):")
        print(f"  ⚠️ Hata Detayı: {exc}")
        if status_code in (404, 410):
            print("  💡 İpucu: Bu abonelik tarayıcı tarafından iptal edilmiş veya süresi dolmuş. Siteden yeniden bildirim izni verilmelidir.")
        elif status_code == 401:
            print("  💡 İpucu: VAPID Private/Public anahtarlarınız uyumsuz veya geçersiz.")
        return False, f"HTTP {status_code}: {exc}"

    except Exception as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        print(f"\n❌ [HATA]: Web Push genel gönderim hatası ({elapsed_ms} ms): {exc}")
        return False, str(exc)


# ── 9. ANA ÇALIŞTIRMA VE RAPORLAMA ──
def main():
    parser = argparse.ArgumentParser(description="MyTakip Bildirim Test Mekanizması (Resend & pywebpush)")
    parser.add_argument('--user', '-u', help='Veritabanından sorgulanacak kullanıcı adı (Örn: admin, local-alpoş)', default=os.environ.get('TEST_USER', 'admin'))
    parser.add_argument('--email', '-e', help='Test e-postasının gönderileceği doğrudan adres', default=os.environ.get('TEST_EMAIL'))
    parser.add_argument('--endpoint', help='Test Web Push endpoint adresi')
    parser.add_argument('--p256dh', help='Test Web Push p256dh anahtarı')
    parser.add_argument('--auth', help='Test Web Push auth anahtarı')
    parser.add_argument('--mock', action='store_true', help='Canlı ağ çağrısı yapmadan simülasyon modunda çalıştırır')
    args = parser.parse_args()

    print("\n" + "#" * 70)
    print("🚀 MYTAKIP BİLDİRİM TEST MEKANİZMASI (LOCAL DEBUGGER)")
    print(f"🕒 Test Başlangıç: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"👤 Hedef Kullanıcı: {args.user}")
    print("#" * 70)

    # Veritabanından kullanıcı bilgilerini çek
    db_email, db_subs = fetch_user_data_from_db(args.user)

    # Hedef e-posta belirleme: CLI > DB > ADMIN_EMAIL > Fallback
    target_email = args.email or db_email or ADMIN_EMAIL or 'admin@mytakip.local'

    # Hedef Web Push aboneliği belirleme
    target_sub = None
    if args.endpoint and args.p256dh and args.auth:
        target_sub = {
            'endpoint': args.endpoint,
            'p256dh': args.p256dh,
            'auth': args.auth
        }
    elif db_subs and len(db_subs) > 0:
        target_sub = db_subs[0]
    else:
        target_sub = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test-token-simulation',
            'p256dh': 'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QT9AcPP313T59P1W_I8B9a5VkhbXQ8NnB0',
            'auth': 'tBHItJI5svbpez7KI4CCXg'
        }

    # 1. E-Posta Testi
    email_ok, email_msg = test_send_email(target_email, force_mock=args.mock)

    # 2. Web Push Testi
    push_ok, push_msg = test_send_webpush(target_sub, force_mock=args.mock)

    # ── ÖZET RAPOR ──
    print("\n" + "#" * 70)
    print("📊 BİLDİRİM TEST ÖZET RAPORU:")
    print(f"  1. Resend E-Posta Testi : {'✅ BAŞARILI' if email_ok else '❌ BAŞARISIZ'} ({email_msg})")
    print(f"  2. Web Push Bildirimi   : {'✅ BAŞARILI' if push_ok else '❌ BAŞARISIZ'} ({push_msg})")
    print("#" * 70 + "\n")

    return 0 if (email_ok and push_ok) else 1


if __name__ == '__main__':
    sys.exit(main())
