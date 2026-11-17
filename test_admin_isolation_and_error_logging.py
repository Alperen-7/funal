#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_admin_isolation_and_error_logging.py
Admin Rolü İzolasyonu, KVKK Maskeleme, Hata Loglama & Saatlik Özet Testi.
"""

import os
import sys
import json
import unittest
from datetime import datetime, timezone

# scripts dizinini sys.path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
import admin_logger
import send_reminders
import send_hourly_admin_summary

class TestAdminIsolationAndErrorLogging(unittest.TestCase):

    def setUp(self):
        # Test için yerel error log dosyasını temizle
        if os.path.exists(admin_logger._LOCAL_LOG_PATH):
            os.remove(admin_logger._LOCAL_LOG_PATH)
        admin_logger._LAST_ALERT_TIMESTAMPS.clear()

    def test_01_admin_role_and_notification_isolation(self):
        print("\n--- 1. TEST: Admin Rolü ve Bildirim İzolasyonu Kontrolü ---")
        
        # 1. Admin kullanıcısı tespiti
        self.assertTrue(send_reminders.is_admin_user('admin'), "Admin kullanıcısı admin olarak algılanmalı!")
        self.assertTrue(send_reminders.is_admin_user('ADMIN'), "Büyük harf ADMIN admin olarak algılanmalı!")
        self.assertFalse(send_reminders.is_admin_user('local-alpoş'), "Standart kullanıcı admin olarak algılanmamalı!")
        self.assertFalse(send_reminders.is_admin_user('normal_user'), "Normal kullanıcı admin olarak algılanmamalı!")
        print("[PASS] is_admin_user() admin rolünü ve standart kullanıcıları başarıyla izole ediyor.")

        # 2. Mock faturalarla run_reminders filtreleme testi
        bills = [
            {'id': 'bill-admin-1', 'title': 'Admin Şirket Faturası', 'amount': 5000, 'username': 'admin'},
            {'id': 'bill-user-1', 'title': 'Kullanıcı Telefon Faturası', 'amount': 250, 'username': 'standart_kullanici'}
        ]

        # send_reminders fonksiyonlarını mockla
        original_get_bills = send_reminders.get_due_unpaid_bills
        original_send_email = send_reminders.send_email_reminder
        original_send_push = send_reminders.send_webpush_reminder
        original_mark_notified = send_reminders.mark_bill_as_notified

        notified_ids = []
        sent_emails = []

        try:
            send_reminders.get_due_unpaid_bills = lambda: bills
            send_reminders.send_email_reminder = lambda email, b, u: sent_emails.append((email, b['id'])) or True
            send_reminders.send_webpush_reminder = lambda s, b, u: True
            send_reminders.mark_bill_as_notified = lambda bid: notified_ids.append(bid) or True
            send_reminders.get_user_email = lambda uname: f"{uname}@example.com"
            send_reminders.get_user_push_subscriptions = lambda uname: []

            send_reminders.run_reminders()

            # Doğrulamalar:
            # Admin'e fatura hatırlatma e-postası KESİNLİKLE gönderilmemeli!
            admin_emails_sent = [item for item in sent_emails if item[1] == 'bill-admin-1']
            self.assertEqual(len(admin_emails_sent), 0, "Admin kullanıcısına standart fatura hatırlatması kesinlikle ATILMAMALI!")
            self.assertIn('bill-admin-1', notified_ids, "Admin faturası filtrelenip döngüden çıkarılmalı.")

            # Standart kullanıcıya e-posta atılmalı
            user_emails_sent = [item for item in sent_emails if item[1] == 'bill-user-1']
            self.assertEqual(len(user_emails_sent), 1, "Standart kullanıcıya fatura bildirimi başarıyla atılmalı.")

            print("[PASS] Admin kullanıcısına standart fatura/ekstre hatırlatmaları %100 engellendi ve filtrelendi.")
        finally:
            send_reminders.get_due_unpaid_bills = original_get_bills
            send_reminders.send_email_reminder = original_send_email
            send_reminders.send_webpush_reminder = original_send_push
            send_reminders.mark_bill_as_notified = original_mark_notified

    def test_02_kvkk_sensitive_data_masking(self):
        print("\n--- 2. TEST: KVKK ve Hassas Veri Maskeleme Kontrolü ---")
        
        # 1. Metin içi maskeleme
        raw_text = "Kullanıcı girişi: pin: 123456, sifre: SuperSecret99, kart: 4543-1234-5678-9012, Bearer eyJhbGciOiJ..."
        masked_text = admin_logger.mask_sensitive_text(raw_text)

        self.assertNotIn("123456", masked_text, "PIN açık metin olarak loglanamaz!")
        self.assertNotIn("SuperSecret99", masked_text, "Şifre açık metin olarak loglanamaz!")
        self.assertNotIn("4543-1234-5678-9012", masked_text, "Kredi kartı numarası açık loglanamaz!")
        self.assertIn("***MASKED***", masked_text)

        # 2. Sözlük (Dictionary) içi hassas anahtar maskeleme
        raw_dict = {
            'username': 'admin',
            'pin': '654321',
            'token': 'secret-token-abc',
            'recoveryKeyHash': 'hash123',
            'details': {
                'password': 'mypassword',
                'credit_card': '5421-9999-8888-7777'
            }
        }
        masked_dict = admin_logger.mask_sensitive_data(raw_dict)
        self.assertEqual(masked_dict['pin'], '***MASKED_SENSITIVE***')
        self.assertEqual(masked_dict['token'], '***MASKED_SENSITIVE***')
        self.assertEqual(masked_dict['details']['password'], '***MASKED_SENSITIVE***')
        self.assertEqual(masked_dict['username'], 'admin')

        print("[PASS] KVKK uyumlu hassas veri maskeleme (PIN, şifre, token, kart) eksiksiz çalışıyor.")

    def test_03_critical_alerts_and_hourly_warnings(self):
        print("\n--- 3. TEST: Kritik Hata Anlık Uyarısı & Saatlik Uyarı Biriktirme ---")

        # Mock resend email function
        sent_alerts = []
        original_send_email = admin_logger.send_resend_email
        admin_logger.send_resend_email = lambda email, sub, html: sent_alerts.append((email, sub, html)) or (True, "mock-id")

        try:
            # 1. Kritik Hata: Anında Admin'e e-posta atmalı
            ok, msg = admin_logger.log_critical(
                "DB_CONNECTION_LOST",
                "Supabase PostgreSQL sunucusuna ulaşılamadı. pin: 123456 bağlantı koptu."
            )
            self.assertTrue(ok)
            self.assertEqual(len(sent_alerts), 1, "Kritik hata anında Admin e-posta uyarısı tetiklemeli!")
            self.assertIn("KRİTİK HATA", sent_alerts[0][1])
            self.assertIn("DB_CONNECTION_LOST", sent_alerts[0][1])
            self.assertNotIn("123456", sent_alerts[0][2], "E-posta şablonunda PIN maskelenmeli!")

            # 2. Debounce / Cooldown testi (10 dakika içinde tekrar aynı hata gelirse e-posta spamı yapmamalı)
            ok2, msg2 = admin_logger.log_critical("DB_CONNECTION_LOST", "Aynı hata tekrarlandı.")
            self.assertFalse(ok2)
            self.assertEqual(len(sent_alerts), 1, "Aynı kritik hata cooldown süresinde tekrar e-posta atmamalı!")
            print("[PASS] Kritik hata anlık alert gönderimi ve spam koruma cooldown mekanizması doğrulandı.")

            # 3. Uyarı (Warning) loglama: E-posta atmaz, saatlik özet için biriktirir
            admin_logger.log_warning("RATE_LIMIT", "TradingView API 429 Too Many Requests")
            admin_logger.log_warning("RATE_LIMIT", "TradingView API 429 Too Many Requests (2)")
            admin_logger.log_warning("AUTH_FAILURE", "Kullanıcı hatalı PIN denemesi")

            # Dosyaya kaydedilen kayıtları doğrula
            self.assertTrue(os.path.exists(admin_logger._LOCAL_LOG_PATH))
            with open(admin_logger._LOCAL_LOG_PATH, 'r', encoding='utf-8') as f:
                records = [json.loads(line) for line in f if line.strip()]

            categories = [r['category'] for r in records]
            self.assertIn("DB_CONNECTION_LOST", categories)
            self.assertIn("RATE_LIMIT", categories)
            self.assertIn("AUTH_FAILURE", categories)
            print("[PASS] Uyarılar saatlik rapor için mt_error_logs / error_logs.jsonl dosyasına başarıyla kaydedildi.")

        finally:
            admin_logger.send_resend_email = original_send_email

    def test_04_hourly_admin_summary_generation(self):
        print("\n--- 4. TEST: Saatlik Hata & Uyarı Özeti Tablo Derleme ---")
        
        # Test için mock kayıtlar
        mock_logs = [
            {'category': 'RATE_LIMIT', 'level': 'WARNING', 'message': 'API istek limiti aşıldı', 'created_at': '2026-11-17T17:00:00Z'},
            {'category': 'RATE_LIMIT', 'level': 'WARNING', 'message': 'API istek limiti aşıldı (2)', 'created_at': '2026-11-17T17:15:00Z'},
            {'category': 'DB_CONNECTION_LOST', 'level': 'CRITICAL', 'message': 'Veritabanı koptu', 'created_at': '2026-11-17T17:20:00Z'}
        ]

        table_html, unique_cats = send_hourly_admin_summary.build_summary_table(mock_logs)
        self.assertEqual(unique_cats, 2)
        self.assertIn("RATE_LIMIT", table_html)
        self.assertIn("DB_CONNECTION_LOST", table_html)
        self.assertIn("CRITICAL", table_html)
        self.assertIn("WARNING", table_html)
        print("[PASS] Saatlik HTML hata özeti tablosu kategorileri ve adetleri kusursuz derliyor.")

    def test_05_test_notifications_cli_debugging(self):
        print("\n--- 5. TEST: test_notifications.py CLI ve Hata Ayıklama İyileştirmeleri ---")
        
        import test_notifications

        # 1. 404 Push tablosu sorgusunda çökmemeli
        email, subs = test_notifications.fetch_user_data_from_db('local-alpoş')
        self.assertIsInstance(subs, list)
        print("[PASS] 404 Client Error tablosu olmayan veritabanında sessizce yakalanıp simülasyon fallback'ine aktarıldı.")

        # 2. Mock modunda test e-postası ve web push başarıyla geçmeli
        email_ok, email_msg = test_notifications.test_send_email('test@example.com', force_mock=True)
        self.assertTrue(email_ok)
        self.assertIn("Simülasyon", email_msg)

        push_ok, push_msg = test_notifications.test_send_webpush({}, force_mock=True)
        self.assertTrue(push_ok)
        self.assertIn("Simülasyon", push_msg)
        print("[PASS] test_notifications.py eksik anahtar durumunda anlaşılır ipucu ve simülasyon ile %100 başarılı çalışıyor.")


if __name__ == '__main__':
    unittest.main()
