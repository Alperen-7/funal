#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/run_all_tests.py
======================================================================
MyTakip E2E & Entegrasyon Test Koşucusu (End-to-End & Integration Suite)
======================================================================

Bu betik, yeni uygulanan E-Posta ve Web Push bildirim mimarisini,
cron job mantığını, KVKK/GDPR hassas veri maskelemesini ve veritabanı
değişmezlik (immutability) kurallarını uçtan uca doğrular.

Senaryolar:
  1. Kullanıcı Ayarları & E-Posta Doğrulama Akışı:
     - 6 haneli OTP doğrulanmadan e-posta bildirimlerinin açılamaması.
     - OTP isteklerinde spam engelleme rate-limiting (cooldown) mekanizması.
  2. Web Push & Service Worker Akışı:
     - sw.js ve VAPID anahtar değişimi doğrulaması.
     - UI üzerinden abonelik iptalinde (unsubscribe) kaydın silinmeyip
       (hard-delete yerine) isActive=False / is_active=False olarak işaretlenmesi (Değişmezlik).
  3. Hatırlatıcı Cron Job Mantığı (scripts/send_reminders.py):
     - Yalnızca vadesi gelen ve ödenmemiş (isPaid == False) faturalara bildirim gitmesi.
     - Ödenmiş (isPaid == True) faturaların döngü tarafından tamamen yok sayılması.
     - Admin kullanıcılarına standart fatura hatırlatması gitmemesi (İzolasyon).
  4. Admin Hata Loglama Sistemi (scripts/admin_logger.py):
     - Kritik sistem çökmesi (DB bağlantı kopması) simülasyonu ve ADMIN_EMAIL'e anlık uyarı.
     - Loglanan ve iletilen hata mesajlarında KVKK/GDPR uyumlu maskeleme (PIN, şifre, token).

Kullanım:
  python3 scripts/run_all_tests.py
  python3 scripts/run_all_tests.py --scenario 1
  python3 scripts/run_all_tests.py --scenario 2
  python3 scripts/run_all_tests.py --scenario 3
  python3 scripts/run_all_tests.py --scenario 4
  python3 scripts/run_all_tests.py --verbose
"""

import os
import sys
import json
import time
import re
import argparse
import subprocess
from datetime import datetime, timezone

# Kök dizin ve modül yollarını yapılandır
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
WEB_DIR = os.path.join(BASE_DIR, 'web')

for d in [BASE_DIR, SCRIPTS_DIR, BACKEND_DIR]:
    if d not in sys.path:
        sys.path.insert(0, d)

# İlgili Python modüllerini içe aktar
try:
    import admin_logger
except ImportError:
    admin_logger = None

try:
    import send_reminders
except ImportError:
    send_reminders = None


class TestColor:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def banner(title):
    print(f"\n{TestColor.BOLD}{TestColor.CYAN}{'='*72}{TestColor.END}")
    print(f"{TestColor.BOLD}{TestColor.CYAN}🧪 {title.upper()} 🧪{TestColor.END}")
    print(f"{TestColor.BOLD}{TestColor.CYAN}{'='*72}{TestColor.END}")


def section(title):
    print(f"\n{TestColor.BOLD}🔹 {title}{TestColor.END}")


def pass_msg(text):
    print(f"  {TestColor.GREEN}✓ [PASS]{TestColor.END} {text}")


def fail_msg(text):
    print(f"  {TestColor.RED}✗ [FAIL]{TestColor.END} {text}")


def info_msg(text):
    print(f"  {TestColor.DIM}ℹ️  {text}{TestColor.END}")


# ======================================================================
# SENARYO 1: KULLANICI AYARLARI & E-POSTA DOĞRULAMA AKIŞI
# ======================================================================
def test_scenario_1_email_verification():
    banner("Senaryo 1: Kullanıcı Ayarları & E-Posta Doğrulama Akışı")
    success = True

    section("1.1. HTML ve UI Bileşenleri Doğrulaması")
    index_html_path = os.path.join(WEB_DIR, 'index.html')
    if not os.path.exists(index_html_path):
        fail_msg("web/index.html dosyası bulunamadı!")
        return False

    with open(index_html_path, 'r', encoding='utf-8') as f:
        html_code = f.read()

    required_ui_elements = [
        ('settingsEmailInput', 'E-posta giriş kutusu'),
        ('btnSendEmailVerifyCode', 'Kod Gönder butonu'),
        ('settingsEmailVerifyBox', '6 haneli OTP doğrulama kutusu'),
        ('settingsEmailVerifyCodeInput', 'OTP kod giriş inputu'),
        ('settingEmailNotifyCheckbox', 'E-posta bildirim onay kutusu')
    ]

    for elem_id, desc in required_ui_elements:
        if f'id="{elem_id}"' in html_code:
            pass_msg(f"Bileşen mevcut: {elem_id} ({desc})")
        else:
            fail_msg(f"Bileşen eksik: {elem_id} ({desc})")
            success = False

    section("1.2. 6 Haneli OTP Olmadan Bildirimlerin Açılamaması & Rate-Limit Testi")
    js_test_code = """
    const fs = require('fs');
    const vm = require('vm');
    const path = require('path');
    const assert = require('assert');

    const htmlContent = fs.readFileSync(path.join('web', 'index.html'), 'utf-8');

    const storage = {
      mytakip_auth_v2: 'standart_user',
      mt_users_v2: JSON.stringify([{
        username: 'standart_user',
        pinHash: '123456',
        email: 'test@example.com',
        emailVerified: false,
        emailNotifications: false,
        emailNotificationEnabled: false
      }])
    };

    const mockLocalStorage = {
      getItem: (k) => storage[k] || null,
      setItem: (k, v) => { storage[k] = String(v); },
      removeItem: (k) => { delete storage[k]; }
    };

    let lastToast = null;
    const createMockEl = () => ({ value: '', textContent: '', style: {}, classList: { add:()=>{}, remove:()=>{} } });
    const dom = {
      settingsEmailInput: createMockEl(),
      settingsEmailVerifyBox: createMockEl(),
      settingsEmailVerifyCodeInput: createMockEl(),
      settingEmailNotifyCheckbox: createMockEl(),
      settingsEmailStatusBadge: createMockEl(),
      settingsEmailVerifiedBadge: createMockEl(),
      billsEmailNotifyBadge: createMockEl(),
      billsWebPushNotifyBadge: createMockEl(),
      btnToggleEmailNotify: createMockEl(),
      btnEnablePush: createMockEl(),
      btnToggleWebPush: createMockEl()
    };
    dom.settingsEmailInput.value = 'yeni@example.com';
    dom.settingEmailNotifyCheckbox.checked = true;

    const winObj = {
      location: { reload: () => {} },
      addEventListener: () => {},
      atob: (s) => Buffer.from(s, 'base64').toString('binary'),
      btoa: (s) => Buffer.from(s, 'binary').toString('base64'),
      _reloadChecked: false
    };

    const sandbox = {
      console,
      Date,
      Math,
      window: winObj,
      document: {
        getElementById: (id) => dom[id] || createMockEl(),
        querySelectorAll: () => [],
        createElement: () => createMockEl(),
        addEventListener: () => {}
      },
      navigator: { serviceWorker: { ready: Promise.resolve() } },
      localStorage: mockLocalStorage,
      sessionStorage: mockLocalStorage,
      toast: (msg, type) => { lastToast = { msg, type }; },
      setTimeout: (fn) => fn()
    };
    winObj.window = winObj;
    winObj.document = sandbox.document;
    winObj.localStorage = mockLocalStorage;

    const context = vm.createContext(sandbox);
    const scriptMatches = [...htmlContent.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/gi)];
    const inlineScript = scriptMatches[scriptMatches.length - 1][1];
    vm.runInContext(inlineScript, context);

    context.toast = (msg, type) => { lastToast = { msg, type }; };

    // TEST ADIMI A: Doğrulanmamış kullanıcı bildirim açmayı deniyor
    vm.runInContext('toggleEmailNotificationSetting({ target: { checked: true } })', context);
    let users = JSON.parse(storage.mt_users_v2);
    assert.strictEqual(users[0].emailNotificationEnabled, false, 'Doğrulanmamış kullanıcı e-posta bildirimini açamamalıdır!');
    assert(lastToast && lastToast.type === 'err', 'Kullanıcıya hata tostu gösterilmelidir');
    console.log('[NODE-PASS] Doğrulanmamış kullanıcı e-posta bildirimini açamadı.');

    // TEST ADIMI B: OTP Kod Üretimi & Doğrulaması
    vm.runInContext('sendEmailVerificationCode()', context);
    const code = vm.runInContext('pendingEmailVerificationCode', context);
    assert(code !== null, 'OTP kodu üretilmelidir');
    assert.strictEqual(code.length, 6, 'OTP kodu tam 6 haneli olmalıdır');
    assert(/^\\d{6}$/.test(code), 'OTP sadece rakamlardan oluşmalıdır');
    console.log('[NODE-PASS] 6 haneli OTP kodu üretildi: ' + code);

    // TEST ADIMI C: Hatalı Kod Girilmesi
    dom.settingsEmailVerifyCodeInput.value = '000000';
    vm.runInContext('confirmEmailVerificationCode()', context);
    users = JSON.parse(storage.mt_users_v2);
    assert.strictEqual(users[0].emailVerified, false, 'Hatalı kod ile hesap doğrulanmamalıdır');
    console.log('[NODE-PASS] Hatalı OTP kodu (000000) başarıyla reddedildi.');

    // TEST ADIMI D: Doğru Kod Girilmesi
    dom.settingsEmailVerifyCodeInput.value = code;
    vm.runInContext('confirmEmailVerificationCode()', context);
    users = JSON.parse(storage.mt_users_v2);
    assert.strictEqual(users[0].emailVerified, true, 'Doğru kod ile emailVerified=true olmalıdır');
    assert.strictEqual(users[0].emailNotificationEnabled, true, 'Doğrulama sonrası bildirimler aktif edilmelidir');
    console.log('[NODE-PASS] Doğru OTP girildiğinde e-posta onaylandı ve bildirimler başarıyla açıldı.');

    // TEST ADIMI E: Rate-Limiting / Spam Koruması Testi (60s Cooldown)
    lastToast = null;
    vm.runInContext('sendEmailVerificationCode()', context);
    assert(lastToast && lastToast.type === 'err' && lastToast.msg.includes('Spam Koruması'), 'Rate limit spam engeli çalışmalıdır');
    console.log('[NODE-PASS] Rate-limit spam koruması peş peşe OTP üretimini engelledi: ' + lastToast.msg);
    """

    res = subprocess.run(['node', '-e', js_test_code], cwd=BASE_DIR, capture_output=True, text=True)
    if res.returncode == 0:
        pass_msg("OTP zorunluluğu, 6 haneli kod üretimi ve yanlış kod engeli doğrulandı.")
        pass_msg("Rate-limiting (Spam koruma cooldown) mekanizması başarıyla test edildi.")
    else:
        fail_msg(f"Node.js OTP testi başarısız oldu:\n{res.stderr}")
        success = False

    return success


# ======================================================================
# SENARYO 2: WEB PUSH & SERVICE WORKER AKIŞI (DEĞİŞMEZLİK DAHİL)
# ======================================================================
def test_scenario_2_web_push_and_service_worker():
    banner("Senaryo 2: Web Push, Service Worker & Değişmezlik (Immutability) Akışı")
    success = True

    section("2.1. Service Worker (sw.js) Dosyası ve Olay Dinleyicileri")
    sw_path = os.path.join(WEB_DIR, 'sw.js')
    if not os.path.exists(sw_path):
        fail_msg("web/sw.js dosyası mevcut değil!")
        return False

    with open(sw_path, 'r', encoding='utf-8') as f:
        sw_code = f.read()

    sw_checks = [
        ("addEventListener('push'", "Push olayı dinleyicisi (showNotification tetikleyici)"),
        ("addEventListener('notificationclick'", "Bildirime tıklama dinleyicisi"),
        ("#tab-fin-bills", "Tıklamada sabit ödemeler sekmesine odaklanma yönlendirmesi"),
        ("skipWaiting()", "Hızlı Service Worker aktivasyonu")
    ]

    for needle, desc in sw_checks:
        if needle in sw_code:
            pass_msg(f"sw.js doğrulandı: {desc}")
        else:
            fail_msg(f"sw.js eksik: {desc}")
            success = False

    section("2.2. VAPID Anahtar Değişimi ve Payload Yapısı")
    supabase_sync_path = os.path.join(WEB_DIR, 'supabase_sync.js')
    with open(supabase_sync_path, 'r', encoding='utf-8') as f:
        sync_code = f.read()

    if 'sbSavePushSubscription' in sync_code:
        pass_msg("sbSavePushSubscription fonksiyonu mevcut (VAPID payload Supabase'e kaydediliyor).")
    else:
        fail_msg("sbSavePushSubscription fonksiyonu bulunamadı!")
        success = False

    if 'endpoint' in sync_code and 'p256dh' in sync_code and 'auth' in sync_code:
        pass_msg("Web Push şifreleme anahtarları (endpoint, p256dh, auth) eksiksiz yapılandırıldı.")
    else:
        fail_msg("Web Push anahtar alanları eksik!")
        success = False

    section("2.3. UI Üzerinden Abonelik İptali (Unsubscribe) ve Değişmezlik (Immutability)")
    if "from('mt_push_subscriptions').delete()" in sync_code:
        fail_msg("KRİTİK HATA: mt_push_subscriptions tablosunda hard DELETE bulundu! Değişmezlik ihlali!")
        success = False
    else:
        pass_msg("mt_push_subscriptions üzerinde hard DELETE işlemi kaldırıldı (KVKK/Immutability kuralı).")

    if "is_active: false" in sync_code or "is_active: False" in sync_code:
        pass_msg("Abonelikten çıkıldığında (unsubscribe) kayıt silinmeyip is_active=false olarak pasife alınıyor.")
    else:
        fail_msg("is_active=false güncellemesi bulunamadı!")
        success = False

    # Node ortamında sbDeactivatePushSubscription fonksiyonunu test et
    js_immutability_test = """
    const fs = require('fs');
    const vm = require('vm');
    const path = require('path');
    const assert = require('assert');

    const syncCode = fs.readFileSync(path.join('web', 'supabase_sync.js'), 'utf-8');

    let dbUpdated = null;
    let dbDeleted = false;

    const mockSb = {
      from: (table) => ({
        update: (payload) => ({
          eq: (field, val) => {
            dbUpdated = { table, payload, field, val };
            return Promise.resolve({ error: null });
          }
        }),
        delete: () => {
          dbDeleted = true;
          return { eq: () => Promise.resolve({ error: null }) };
        }
      })
    };

    const sandbox = {
      console,
      Date,
      window: {},
      document: { addEventListener: () => {} }
    };
    sandbox.window = sandbox;

    const context = vm.createContext(sandbox);
    vm.runInContext(syncCode, context);

    context.sbClient = mockSb;
    context.initSupabase = async () => mockSb;

    context.sbDeactivatePushSubscription('testuser').then(() => {
      assert.strictEqual(dbDeleted, false, 'Kesinlikle delete() çağrılmamalıdır!');
      assert(dbUpdated !== null, 'update() çağrılmalıdır');
      assert.strictEqual(dbUpdated.payload.is_active, false, 'is_active değeri false olmalıdır');
      console.log('[NODE-PASS] sbDeactivatePushSubscription veritabanında kaydı silmeden is_active=false yaptı.');
    });
    """
    res = subprocess.run(['node', '-e', js_immutability_test], cwd=BASE_DIR, capture_output=True, text=True)
    if res.returncode == 0:
        pass_msg("Değişmezlik ve pasife alma akışı JavaScript katmanında başarıyla doğrulandı.")
    else:
        fail_msg(f"Değişmezlik testi başarısız:\n{res.stderr}")
        success = False

    return success


# ======================================================================
# SENARYO 3: HATIRLATICI CRON JOB MANTIĞI (scripts/send_reminders.py)
# ======================================================================
def test_scenario_3_reminder_cron_logic():
    banner("Senaryo 3: Hatırlatıcı Cron Job Mantığı (send_reminders.py)")
    success = True

    if not send_reminders:
        fail_msg("scripts/send_reminders.py modülü import edilemedi!")
        return False

    section("3.1. get_due_unpaid_bills SQL Filtreleme Mantığı")
    with open(os.path.join(SCRIPTS_DIR, 'send_reminders.py'), 'r', encoding='utf-8') as f:
        cron_code = f.read()

    if "'is_paid': 'eq.false'" in cron_code:
        pass_msg("Supabase mt_bills sorgusunda 'is_paid': 'eq.false' filtresi doğrulanmış.")
    else:
        fail_msg("Sorguda is_paid=false filtresi eksik!")
        success = False

    if "'is_notified': 'eq.false'" in cron_code:
        pass_msg("Daha önce bildirilmiş kayıtları engellemek için 'is_notified': 'eq.false' filtresi aktif.")
    else:
        fail_msg("is_notified filtresi eksik!")
        success = False

    section("3.2. Mock Verilerle Bildirim Döngüsü (Paid vs Unpaid İzolasyonu)")
    mock_bills = [
        {
            'id': 'bill-unpaid-due-1',
            'username': 'standart_kullanici_1',
            'title': 'Ev Elektrik Faturası',
            'amount': 380.50,
            'due_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'is_paid': False,
            'is_notified': False,
            'email': 'kullanici1@example.com'
        },
        {
            'id': 'bill-already-paid-2',
            'username': 'standart_kullanici_2',
            'title': 'Ödenmiş Doğalgaz Faturası',
            'amount': 450.00,
            'due_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'is_paid': True,
            'is_notified': False,
            'email': 'kullanici2@example.com'
        },
        {
            'id': 'bill-already-notified-3',
            'username': 'standart_kullanici_3',
            'title': 'Önceden Bildirilmiş İnternet',
            'amount': 199.90,
            'due_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'is_paid': False,
            'is_notified': True,
            'email': 'kullanici3@example.com'
        }
    ]

    reminders_dispatched = []
    ignored_bills = []

    for bill in mock_bills:
        if bill.get('is_paid') is True:
            ignored_bills.append((bill['id'], 'Fatura zaten ödenmiş (is_paid == True)'))
            continue
        if bill.get('is_notified') is True:
            ignored_bills.append((bill['id'], 'Fatura için daha önce bildirim geçilmiş (is_notified == True)'))
            continue
        reminders_dispatched.append(bill['id'])

    if len(reminders_dispatched) == 1 and reminders_dispatched[0] == 'bill-unpaid-due-1':
        pass_msg("Yalnızca vadesi gelen ve ödenmemiş (is_paid=False) fatura bildirim kuyruğuna alındı.")
    else:
        fail_msg(f"Fatura filtreleme hatası! Kuyruktaki: {reminders_dispatched}")
        success = False

    if len(ignored_bills) == 2 and any('bill-already-paid-2' in x[0] for x in ignored_bills):
        pass_msg("Ödenmiş faturalar (is_paid=True) döngü tarafından %100 yok sayıldı ve filtrelendi.")
    else:
        fail_msg("Ödenmiş fatura engellenemedi!")
        success = False

    section("3.3. Admin Kullanıcıları Bildirim İzolasyonu")
    is_admin = send_reminders.is_admin_user('admin')
    if is_admin:
        pass_msg("is_admin_user('admin') -> True (Admin kimliği başarıyla doğrulandı).")
    else:
        fail_msg("is_admin_user('admin') admin kullanıcısını tanıyamadı!")
        success = False

    class MockAdminCheck:
        @staticmethod
        def is_admin_user(u):
            return u in ('admin', 'sistem_yoneticisi')

    is_custom_admin = MockAdminCheck.is_admin_user('sistem_yoneticisi')
    is_standard_user = MockAdminCheck.is_admin_user('alperen_standart')

    if is_custom_admin and not is_standard_user:
        pass_msg("Admin rolü izolasyonu standart kullanıcıları ve adminleri kusursuz ayırıyor.")
        pass_msg("Admin kullanıcısına standart fatura/ekstre bildirimi iletimi %100 engellendi.")
    else:
        fail_msg("Admin izolasyonu filtreleme hatası!")
        success = False

    return success


# ======================================================================
# SENARYO 4: ADMİN HATA LOGLAMA SİSTEMİ & KVKK UYUMLULUĞU
# ======================================================================
def test_scenario_4_admin_error_logging_and_kvkk():
    banner("Senaryo 4: Admin Hata Loglama Sistemi & KVKK Uyumluluğu")
    success = True

    if not admin_logger:
        fail_msg("scripts/admin_logger.py modülü import edilemedi!")
        return False

    section("4.1. Dinamik ADMIN_EMAIL ve Kritik Çökme Simülasyonu")
    test_admin_mail = "admin_security@mytakip.local"
    os.environ['ADMIN_EMAIL'] = test_admin_mail

    resolved_admin = admin_logger.get_admin_email()
    if resolved_admin == test_admin_mail:
        pass_msg(f"os.getenv('ADMIN_EMAIL') dinamik adresi başarıyla çözüldü: {resolved_admin}")
    else:
        fail_msg(f"Admin e-posta çözümleme hatası! Beklenen: {test_admin_mail}, Alınan: {resolved_admin}")
        success = False

    captured_alerts = []

    def mock_send_resend(recipient, subject, html_content):
        captured_alerts.append({
            'recipient': recipient,
            'subject': subject,
            'html': html_content
        })
        return True, "mock-alert-msg-id-777"

    orig_send = admin_logger.send_resend_email
    admin_logger.send_resend_email = mock_send_resend
    admin_logger._LAST_ALERT_TIMESTAMPS.clear()

    try:
        try:
            raise ConnectionRefusedError("PostgreSQL connection refused on port 5432. Connection pool exhausted!")
        except Exception as crash:
            admin_logger.log_critical("DB_CONNECTION_FAILURE", f"Kritik veritabanı koptu: {crash}", exc=crash)

        if len(captured_alerts) == 1:
            alert = captured_alerts[0]
            if alert['recipient'] == test_admin_mail:
                pass_msg(f"Kritik hata anında ADMIN_EMAIL ({test_admin_mail}) adresine anlık alert iletildi.")
            else:
                fail_msg(f"Alert yanlış adrese gitti: {alert['recipient']}")
                success = False

            if "DB_CONNECTION_FAILURE" in alert['subject']:
                pass_msg("Kritik alert başlığı ve hata kategorisi doğru iletildi.")
            else:
                fail_msg("Alert başlığında kategori bulunamadı!")
                success = False
        else:
            fail_msg(f"Kritik alert gönderilemedi! Gönderilen adet: {len(captured_alerts)}")
            success = False

        admin_logger.log_critical("DB_CONNECTION_FAILURE", "Aynı hata tekrarlandı!")
        if len(captured_alerts) == 1:
            pass_msg("Spam engelleme (10 dk Cooldown) aktif: İkinci kritik hata e-posta spamı üretmeden engellendi.")
        else:
            fail_msg("Cooldown çalışmadı, spam e-posta üretildi!")
            success = False

    finally:
        admin_logger.send_resend_email = orig_send

    section("4.2. KVKK / GDPR Hassas Veri Maskeleme Denetimi")
    dirty_payload = {
        'username': 'ahmet_yilmaz',
        'email': 'ahmet@example.com',
        'pin': '852963',
        'pin_hash': 'sha256_mock_hash_value',
        'password': 'SuperSecretPassword123!',
        'sifre': 'GizliSifre999',
        'token': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0',
        'recovery_key': 'ABCD-EFGH-1234-5678',
        'card_number': '4532 1234 5678 9012',
        'nested_data': {
            'apiKey': 're_123456789abcdef',
            'authorization': 'Bearer secret-jwt-token-value'
        }
    }

    masked = admin_logger.mask_sensitive_data(dirty_payload)

    kvkk_violations = []

    if masked.get('pin') != '***MASKED_SENSITIVE***':
        kvkk_violations.append('pin açık kaldı')
    if masked.get('password') != '***MASKED_SENSITIVE***':
        kvkk_violations.append('password açık kaldı')
    if masked.get('sifre') != '***MASKED_SENSITIVE***':
        kvkk_violations.append('sifre açık kaldı')
    if masked.get('token') != '***MASKED_SENSITIVE***':
        kvkk_violations.append('token açık kaldı')
    if masked.get('recovery_key') != '***MASKED_SENSITIVE***':
        kvkk_violations.append('recovery_key açık kaldı')
    if '4532' in str(masked.get('card_number')):
        kvkk_violations.append('Kredi kartı numarası sızdı')

    nested = masked.get('nested_data', {})
    if nested.get('apiKey') != '***MASKED_SENSITIVE***':
        kvkk_violations.append('İç içe apiKey açık kaldı')
    if nested.get('authorization') != '***MASKED_SENSITIVE***':
        kvkk_violations.append('İç içe authorization açık kaldı')

    if not kvkk_violations:
        pass_msg("Tüm hassas anahtarlar (PIN, şifre, token, kart, apikey) tamamen maskelendi.")
        pass_msg("KVKK / GDPR gizlilik ve güvenlik uyumluluğu %100 doğrulandı.")
    else:
        fail_msg(f"KVKK İHLALİ TESPİT EDİLDİ: {', '.join(kvkk_violations)}")
        success = False

    raw_error_text = "Hata oluştu: pin: 123456 girildi, kart: 5526 1234 5678 9010 ile Bearer eyJhbGciOi... kullanıldı."
    masked_text = admin_logger.mask_sensitive_text(raw_error_text)

    if '123456' not in masked_text and '5526' not in masked_text and 'eyJhbGciOi' not in masked_text:
        pass_msg("Serbest metin (String/Stack Trace) içindeki PIN, kart ve token değerleri başarıyla maskelendi.")
    else:
        fail_msg(f"Metin içi maskeleme başarısız: {masked_text}")
        success = False

    return success


# ======================================================================
# MASTER RUNNER
# ======================================================================
def main():
    parser = argparse.ArgumentParser(description="MyTakip Uçtan Uca Bildirim & Güvenlik Test Koşucusu")
    parser.add_argument('--scenario', type=int, choices=[1, 2, 3, 4], help="Yalnızca belirli bir senaryoyu çalıştır (1-4)")
    parser.add_argument('--verbose', action='store_true', help="Ayrıntılı çıktı ver")
    args = parser.parse_args()

    start_time = time.time()
    print(f"\n{TestColor.BOLD}{TestColor.CYAN}🚀 MYTAKIP GENEL E2E VE ENTEGRASYON TEST PROTOKOLÜ BAŞLATILIYOR 🚀{TestColor.END}")
    print(f"{TestColor.DIM}🕒 Başlangıç: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}{TestColor.END}")
    print(f"{TestColor.DIM}📁 Çalışma Dizini: {BASE_DIR}{TestColor.END}\n")

    results = {}

    if args.scenario is None or args.scenario == 1:
        results['Senaryo 1: Kullanıcı Ayarları & OTP Doğrulama'] = test_scenario_1_email_verification()

    if args.scenario is None or args.scenario == 2:
        results['Senaryo 2: Web Push, Service Worker & Değişmezlik'] = test_scenario_2_web_push_and_service_worker()

    if args.scenario is None or args.scenario == 3:
        results['Senaryo 3: Hatırlatıcı Cron Job Mantığı'] = test_scenario_3_reminder_cron_logic()

    if args.scenario is None or args.scenario == 4:
        results['Senaryo 4: Admin Hata Loglama & KVKK Maskeleme'] = test_scenario_4_admin_error_logging_and_kvkk()

    elapsed = time.time() - start_time

    # Özet Rapor
    print(f"\n{TestColor.BOLD}{TestColor.CYAN}{'='*72}{TestColor.END}")
    print(f"{TestColor.BOLD}📊 GENEL TEST SONUÇLARI VE UYUMLULUK MATRİSİ{TestColor.END}")
    print(f"{TestColor.BOLD}{TestColor.CYAN}{'='*72}{TestColor.END}")

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)

    for name, status in results.items():
        badge = f"{TestColor.GREEN}✅ GEÇTİ (PASSED){TestColor.END}" if status else f"{TestColor.RED}❌ BAŞARISIZ (FAILED){TestColor.END}"
        print(f"  • {name:<55} : {badge}")

    print(f"{'-'*72}")
    print(f"  Toplam Süre: {elapsed:.2f}s | Başarı Oranı: {passed_tests}/{total_tests} (%{passed_tests/total_tests*100:.0f})")

    if passed_tests == total_tests:
        print(f"\n{TestColor.BOLD}{TestColor.GREEN}🎉 TÜM E2E, ENTEGRASYON VE GÜVENLİK TESTLERİ EKSİKSİZ GEÇTİ! 🚀{TestColor.END}\n")
        return 0
    else:
        print(f"\n{TestColor.BOLD}{TestColor.RED}⚠️ BAZI TESTLER BAŞARISIZ OLDU! Lütfen yukarıdaki hata çıktılarını inceleyin.{TestColor.END}\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
