import os
import sys
import json
import logging
import warnings
from datetime import datetime, timezone

# macOS LibreSSL / urllib3 uyarılarını bastır
warnings.filterwarnings('ignore', message='.*urllib3 v2 only supports OpenSSL.*')
warnings.filterwarnings('ignore', category=UserWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import admin_logger
except ImportError:
    admin_logger = None

try:
    import requests
except ImportError:
    requests = None
    import urllib.request
    import urllib.error
    import urllib.parse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('RemindersCron')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'MyTakip <onboarding@resend.dev>')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS_SUB = os.environ.get('VAPID_CLAIMS_SUB', 'mailto:admin@mytakip.local')
APP_URL = os.environ.get('APP_URL', 'https://alperen-7.github.io/funal')

def is_admin_user(username):
    if not username:
        return False
    u = str(username).strip().lower()
    if u == 'admin':
        return True
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    url = f"{SUPABASE_URL}/rest/v1/mt_users"
    params = {'username': f'eq.{u}', 'select': 'is_admin,role,username'}
    try:
        data = api_get(url, params=params)
        if data and len(data) > 0:
            row = data[0]
            is_adm = row.get('is_admin')
            role = str(row.get('role') or '').lower()
            return bool(is_adm) or (role == 'admin')
    except Exception as exc:
        logger.warning(f"Admin kontrolü sorgusu hatası ({username}): {exc}")
    return False

try:
    import resend
    if RESEND_API_KEY:
        resend.api_key = RESEND_API_KEY
except ImportError:
    resend = None

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None
    WebPushException = Exception


def get_headers():
    return {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }


def api_get(url, params=None):
    if requests:
        resp = requests.get(url, headers=get_headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    else:
        full_url = url
        if params:
            query = urllib.parse.urlencode(params)
            full_url = f"{url}?{query}"
        req = urllib.request.Request(full_url, headers=get_headers(), method='GET')
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))


def api_patch(url, payload):
    if requests:
        resp = requests.patch(url, headers=get_headers(), json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    else:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=get_headers(),
            method='PATCH'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))


def get_due_unpaid_bills():
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning('SUPABASE_URL veya SUPABASE_KEY tanımlı değil. DB sorgusu atlandı.')
        return []

    today = datetime.now(timezone.utc)
    today_str = today.strftime('%Y-%m-%d')
    today_day = today.day

    url = f"{SUPABASE_URL}/rest/v1/mt_bills"
    params = {
        'select': '*',
        'is_paid': 'eq.false',
        'is_notified': 'eq.false'
    }

    try:
        raw_bills = api_get(url, params=params)
    except Exception as exc:
        logger.error(f'mt_bills tablosu sorgulanırken hata: {exc}')
        if admin_logger:
            admin_logger.log_critical("DB_CONNECTION_LOST", f"mt_bills sorgusu başarısız, veritabanı bağlantısı koptu: {exc}", exc=exc)
        return []

    due_bills = []
    for bill in raw_bills:
        due_day = bill.get('due_day')
        due_date = bill.get('due_date') or bill.get('dueDate')

        is_due = False
        if due_date:
            is_due = str(due_date).startswith(today_str)
        elif due_day is not None:
            is_due = int(due_day) == today_day

        if is_due:
            due_bills.append(bill)

    logger.info(f'Bugün vadesi gelen ödenmemiş fatura sayısı: {len(due_bills)}')
    return due_bills


def get_user_email(username):
    if not SUPABASE_URL or not SUPABASE_KEY or not username:
        return None

    url = f"{SUPABASE_URL}/rest/v1/mt_users"
    params = {'username': f'eq.{username.lower()}', 'select': 'email'}
    try:
        data = api_get(url, params=params)
        if data and data[0].get('email'):
            return data[0]['email']
    except Exception as exc:
        logger.warning(f'Kullanıcı e-posta sorgusu hatası ({username}): {exc}')
    return None


def get_user_push_subscriptions(username):
    if not SUPABASE_URL or not SUPABASE_KEY or not username:
        return []

    url = f"{SUPABASE_URL}/rest/v1/mt_push_subscriptions"
    params = {'username': f'eq.{username.lower()}', 'select': '*'}
    try:
        return api_get(url, params=params)
    except Exception as exc:
        err_str = str(exc)
        if '404' in err_str or 'Not Found' in err_str:
            logger.info("ℹ️ mt_push_subscriptions tablosu veritabanında henüz oluşturulmamış (404 Not Found).")
        else:
            logger.warning(f'Web Push abonelik sorgusu hatası ({username}): {exc}')
            if admin_logger:
                admin_logger.log_warning("PUSH_SUBSCRIPTION_QUERY_ERROR", str(exc), exc=exc)
    return []


def format_currency(amount):
    try:
        val = float(amount)
        return f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + " ₺"
    except (ValueError, TypeError):
        return f"{amount} ₺"


def send_email_reminder(recipient_email, bill, app_url):
    if not resend or not RESEND_API_KEY:
        logger.warning('Resend kütüphanesi veya RESEND_API_KEY bulunamadı, e-posta atlanıyor.')
        return False

    if not recipient_email or '@' not in recipient_email:
        logger.warning(f'Geçersiz alıcı e-posta adresi: {recipient_email}')
        return False

    title = bill.get('title') or bill.get('name') or 'Fatura / Kredi Kartı'
    amount_str = format_currency(bill.get('amount', 0))
    today_str = datetime.now(timezone.utc).strftime('%d.%m.%Y')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Yaklaşan Ödeme Hatırlatması</title>
      <style>
        body {{ margin: 0; padding: 0; background-color: #080b12; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f8fafc; }}
        .wrapper {{ max-width: 580px; margin: 30px auto; background-color: #0f1422; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #4f46e5, #6366f1); padding: 28px 24px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 22px; color: #ffffff; font-weight: 700; }}
        .content {{ padding: 32px 28px; }}
        .alert-badge {{ display: inline-block; background-color: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; padding: 6px 14px; border-radius: 9999px; font-size: 13px; font-weight: 600; margin-bottom: 20px; }}
        .card {{ background-color: #161c2e; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 20px; margin: 18px 0; }}
        .card-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 14px; }}
        .card-row:last-child {{ border-bottom: none; }}
        .label {{ color: #94a3b8; }}
        .value {{ color: #f8fafc; font-weight: 600; }}
        .amount {{ color: #ef4444; font-size: 24px; font-weight: 800; text-align: center; margin: 12px 0; }}
        .btn-wrap {{ text-align: center; margin-top: 28px; }}
        .btn {{ display: inline-block; background-color: #6366f1; color: #ffffff; text-decoration: none; padding: 13px 32px; border-radius: 10px; font-weight: 600; font-size: 15px; box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4); }}
        .footer {{ text-align: center; padding: 20px 24px; font-size: 12px; color: #64748b; border-top: 1px solid rgba(255,255,255,0.05); }}
      </style>
    </head>
    <body>
      <div class="wrapper">
        <div class="header">
          <h1>🔔 MyTakip Ödeme Hatırlatması</h1>
        </div>
        <div class="content">
          <div style="text-align: center;">
            <span class="alert-badge">⏰ Son Ödeme Tarihi: Bugün ({today_str})</span>
          </div>
          <p style="font-size: 15px; line-height: 1.6; color: #94a3b8; margin-top: 10px;">
            Merhaba, sistemde kayıtlı olan <strong>{title}</strong> ödemenizin son günü gelmiştir. Gecikme faizine veya aksamaya uğramaması adına ödemenizi gerçekleştirmeniz tavsiye edilir.
          </p>
          <div class="card">
            <div class="amount">{amount_str}</div>
            <div class="card-row">
              <span class="label">Ödeme Kalemi:</span>
              <span class="value">{title}</span>
            </div>
            <div class="card-row">
              <span class="label">Vade Tarihi:</span>
              <span class="value">{today_str}</span>
            </div>
            <div class="card-row">
              <span class="label">Durum:</span>
              <span class="value" style="color: #f87171;">Ödenmedi</span>
            </div>
          </div>
          <div class="btn-wrap">
            <a href="{app_url}#tab-fin-bills" class="btn">💳 Ödemeyi İncele & Kaydet</a>
          </div>
        </div>
        <div class="footer">
          Bu otomatik hatırlatma MyTakip Akıllı Bütçe & Finans Motoru tarafından gönderilmiştir.<br>
          Kayıtlarınız değişmezlik (immutable) prensibi gereğince saklanmaktadır.
        </div>
      </div>
    </body>
    </html>
    """

    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [recipient_email],
            "subject": f"⏰ Yaklaşan Ödeme: {title} ({amount_str})",
            "html": html_content
        }
        res = resend.Emails.send(params)
        logger.info(f"E-posta başarıyla iletildi: {recipient_email} - ID: {res.get('id') if isinstance(res, dict) else res}")
        return True
    except Exception as exc:
        logger.error(f"E-posta gönderiminde hata: {exc}")
        return False


def send_webpush_reminder(subscription, bill, app_url):
    if not webpush or not VAPID_PRIVATE_KEY:
        logger.warning('pywebpush veya VAPID_PRIVATE_KEY bulunamadı, Web Push atlanıyor.')
        return False

    title = bill.get('title') or bill.get('name') or 'Fatura'
    amount_str = format_currency(bill.get('amount', 0))

    sub_info = {
        'endpoint': subscription.get('endpoint'),
        'keys': {
            'p256dh': subscription.get('p256dh'),
            'auth': subscription.get('auth')
        }
    }

    payload = json.dumps({
        'title': f'⏰ Son Gün: {title}',
        'body': f'{amount_str} tutarındaki ödemenizin son günü. Detaylar için tıklayın.',
        'icon': f'{app_url}/favicon.ico',
        'badge': f'{app_url}/favicon.ico',
        'url': f'{app_url}#tab-fin-bills',
        'tag': f"bill-{bill.get('id')}",
        'data': {
            'billId': bill.get('id'),
            'amount': bill.get('amount')
        }
    })

    try:
        webpush(
            subscription_info=sub_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_CLAIMS_SUB}
        )
        logger.info(f"Web Push bildirimi başarıyla iletildi: {subscription.get('endpoint')[:45]}...")
        return True
    except WebPushException as exc:
        status_code = getattr(exc.response, 'status_code', None) if hasattr(exc, 'response') else None
        if status_code in (404, 410):
            logger.warning(f"Push aboneliği süresi dolmuş veya iptal edilmiş (HTTP {status_code}): {subscription.get('id')}")
        else:
            logger.error(f"Web Push iletim hatası (HTTP {status_code}): {exc}")
        return False
    except Exception as exc:
        logger.error(f"Web Push genel hata: {exc}")
        return False


def mark_bill_as_notified(bill_id):
    if not SUPABASE_URL or not SUPABASE_KEY or not bill_id:
        return False

    url = f"{SUPABASE_URL}/rest/v1/mt_bills?id=eq.{bill_id}"
    payload = {
        'is_notified': True,
        'notified_at': datetime.now(timezone.utc).isoformat()
    }
    try:
        api_patch(url, payload)
        logger.info(f"Kayıt güncellendi (is_notified=True): Fatura ID {bill_id}")
        return True
    except Exception as exc:
        logger.error(f"Fatura durum güncelleme hatası ({bill_id}): {exc}")
        return False


def run_reminders():
    logger.info("=== MyTakip Günlük Ödeme Hatırlatıcı Cron Başladı ===")
    bills = get_due_unpaid_bills()
    if not bills:
        logger.info("Bugün vadesi gelen veya bildirim bekleyen fatura bulunamadı.")
        return

    processed = 0
    notified = 0

    for bill in bills:
        bill_id = bill.get('id')
        username = bill.get('username')
        title = bill.get('title') or bill.get('name')
        processed += 1

        if is_admin_user(username):
            logger.info(f"🚫 Admin kullanıcısı ({username}) için standart fatura hatırlatması filtrelendi/engellendi (Fatura: {title}).")
            mark_bill_as_notified(bill_id)
            notified += 1
            continue

        logger.info(f"İşleniyor [{processed}/{len(bills)}]: {title} (Kullanıcı: {username})")

        push_sent = False
        subscriptions = get_user_push_subscriptions(username)
        for sub in subscriptions:
            success = send_webpush_reminder(sub, bill, APP_URL)
            if success:
                push_sent = True

        email_sent = False
        user_email = bill.get('email') or get_user_email(username)
        if user_email:
            email_sent = send_email_reminder(user_email, bill, APP_URL)

        if push_sent or email_sent or not (subscriptions or user_email):
            mark_bill_as_notified(bill_id)
            notified += 1

    logger.info(f"=== Cron Tamamlandı: {len(bills)} faturadan {notified} adedi için bildirim süreci başarıyla yürütüldü. ===")


def run_test_email(target_email):
    logger.info(f"=== Test E-Posta Gönderimi Başlatılıyor: {target_email} ===")
    mock_bill = {
        'id': 'test-bill-001',
        'title': 'Test Kredi Kartı Ekstresi / Elektrik Faturası',
        'amount': 1450.75,
        'due_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'username': 'test_user'
    }
    success = send_email_reminder(target_email, mock_bill, APP_URL)
    if success:
        logger.info(f"✓ Test e-postası başarıyla gönderildi! Lütfen {target_email} gelen kutunuzu (veya spam klasörünü) kontrol edin.")
    else:
        logger.error("❌ Test e-postası gönderilemedi. Lütfen RESEND_API_KEY ve SENDER_EMAIL ayarlarınızı kontrol edin.")
    return success


def run_dry_run():
    logger.info("=== DRY-RUN (Simülasyon Modu) Başlatıldı - Veritabanı Değiştirilmeyecek ===")
    bills = get_due_unpaid_bills()
    logger.info(f"Bulunan vadesi gelmiş ödenmemiş fatura sayısı: {len(bills)}")
    for i, b in enumerate(bills, 1):
        title = b.get('title') or b.get('name') or 'İsimsiz'
        amt = format_currency(b.get('amount', 0))
        uname = b.get('username', 'belirsiz')
        is_adm = is_admin_user(uname)
        adm_tag = " [ADMIN - Standart bildirimlerden muaf/filtrelendi]" if is_adm else ""
        email = b.get('email') or get_user_email(uname)
        subs = get_user_push_subscriptions(uname)
        logger.info(f"  [{i}] {title} - {amt} | Kullanıcı: {uname}{adm_tag} | E-posta: {email or 'Kayıtlı değil'} | Push Abonelikleri: {len(subs)} cihaz")
    logger.info("=== Simülasyon tamamlandı. ===")


def check_status():
    logger.info("=== MyTakip Bildirim Servisi Durum Raporu ===")
    logger.info(f"Supabase URL: {'Tanımlı (' + SUPABASE_URL[:25] + '...)' if SUPABASE_URL else 'Eksik ❌'}")
    logger.info(f"Supabase Key: {'Tanımlı (Gizlendi)' if SUPABASE_KEY else 'Eksik ❌'}")
    logger.info(f"Resend API Key: {'Tanımlı (Gizlendi)' if RESEND_API_KEY else 'Eksik ❌'}")
    logger.info(f"Sender Email: {SENDER_EMAIL}")
    logger.info(f"VAPID Private Key: {'Tanımlı (Gizlendi)' if VAPID_PRIVATE_KEY else 'Eksik ❌'}")
    logger.info(f"VAPID Public Key: {'Tanımlı' if VAPID_PUBLIC_KEY else 'Eksik ❌'}")
    logger.info(f"App URL: {APP_URL}")
    logger.info("===========================================")


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--status' in args:
        check_status()
    elif '--dry-run' in args:
        run_dry_run()
    elif '--test-email' in args:
        idx = args.index('--test-email')
        if idx + 1 < len(args):
            run_test_email(args[idx + 1])
        else:
            logger.error("Lütfen hedef e-posta adresini belirtin: --test-email ornek@domain.com")
    else:
        run_reminders()
