#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/send_hourly_admin_summary.py
Saatlik Hata ve Uyarı Özeti Gönderici (Hourly Error Summary Cron Job).

Kullanım:
  python3 scripts/send_hourly_admin_summary.py
  python3 scripts/send_hourly_admin_summary.py --force
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone, timedelta

# macOS LibreSSL uyarısını bastır
import warnings
warnings.filterwarnings('ignore', message='.*urllib3 v2 only supports OpenSSL.*')
warnings.filterwarnings('ignore', category=UserWarning)

# Modül yolunu ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import admin_logger
from admin_logger import (
    SUPABASE_URL, SUPABASE_KEY, RESEND_API_KEY,
    get_admin_email, send_resend_email, mask_sensitive_text, _LOCAL_LOG_PATH
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [HourlySummary] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('HourlySummary')

try:
    import requests
except ImportError:
    requests = None
    import urllib.request
    import urllib.error
    import urllib.parse


def fetch_unreported_logs(hours=1):
    cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    logs = []

    # 1. Supabase mt_error_logs tablosundan çekme
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/mt_error_logs"
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json'
            }
            params = {
                'select': '*',
                'created_at': f'gte.{cutoff_time}',
                'order': 'created_at.desc'
            }
            if requests:
                r = requests.get(url, headers=headers, params=params, timeout=10)
                if r.status_code == 200:
                    logs = r.json()
            else:
                full_url = f"{url}?{urllib.parse.urlencode(params)}"
                req = urllib.request.Request(full_url, headers=headers, method='GET')
                with urllib.request.urlopen(req, timeout=10) as resp:
                    logs = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            logger.warning(f"Supabase mt_error_logs sorgusu başarısız (yerel dosya kontrol edilecek): {e}")

    # 2. Yerel JSONL dosyasından çekme (Supabase boşsa veya erişilemiyorsa)
    if not logs and os.path.exists(_LOCAL_LOG_PATH):
        try:
            with open(_LOCAL_LOG_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        rec_time = record.get('created_at', '')
                        if rec_time >= cutoff_time:
                            logs.append(record)
        except Exception as e:
            logger.warning(f"Yerel log dosyası okuma hatası: {e}")

    return logs


def mark_logs_as_notified(log_ids):
    if not SUPABASE_URL or not SUPABASE_KEY or not log_ids:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/mt_error_logs"
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
        }
        payload = {
            'is_notified': True,
            'notified_at': datetime.now(timezone.utc).isoformat()
        }
        for lid in log_ids:
            patch_url = f"{url}?id=eq.{lid}"
            if requests:
                requests.patch(patch_url, headers=headers, json=payload, timeout=5)
            else:
                req = urllib.request.Request(patch_url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PATCH')
                with urllib.request.urlopen(req, timeout=5):
                    pass
    except Exception:
        pass


def build_summary_table(logs):
    # Kategoriye göre gruplama
    grouped = {}
    for log in logs:
        cat = log.get('category', 'GENEL')
        lvl = log.get('level', 'WARNING')
        msg = log.get('message', '')
        created = log.get('created_at', '')

        if cat not in grouped:
            grouped[cat] = {
                'category': cat,
                'level': lvl,
                'count': 0,
                'first_seen': created,
                'last_seen': created,
                'sample_msg': msg
            }
        grouped[cat]['count'] += 1
        if created < grouped[cat]['first_seen']:
            grouped[cat]['first_seen'] = created
        if created > grouped[cat]['last_seen']:
            grouped[cat]['last_seen'] = created
            grouped[cat]['sample_msg'] = msg

    rows_html = ""
    for cat, data in sorted(grouped.items(), key=lambda x: x[1]['count'], reverse=True):
        is_crit = data['level'] == 'CRITICAL'
        lvl_color = "#ef4444" if is_crit else "#f59e0b"
        lvl_bg = "rgba(239,68,68,0.15)" if is_crit else "rgba(245,158,11,0.15)"

        first_fmt = data['first_seen'][11:19] if len(data['first_seen']) >= 19 else data['first_seen']
        last_fmt = data['last_seen'][11:19] if len(data['last_seen']) >= 19 else data['last_seen']

        rows_html += f"""
        <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
          <td style="padding:10px 12px; font-weight:700;"><span style="background:{lvl_bg}; color:{lvl_color}; padding:3px 8px; border-radius:4px; font-size:11px;">{data['level']}</span></td>
          <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">{cat}</td>
          <td style="padding:10px 12px; text-align:center; font-weight:800; color:#6366f1;">{data['count']}</td>
          <td style="padding:10px 12px; font-size:12px; color:#94a3b8;">{first_fmt} - {last_fmt}</td>
          <td style="padding:10px 12px; font-size:12px; color:#cbd5e1; font-family:monospace;">{mask_sensitive_text(data['sample_msg'][:110])}{'...' if len(data['sample_msg']) > 110 else ''}</td>
        </tr>
        """
    return rows_html, len(grouped)


def send_hourly_summary(force=False):
    admin_email = get_admin_email()
    logger.info(f"=== Saatlik Admin Hata Özeti Cron Başladı (Admin: {admin_email}) ===")

    logs = fetch_unreported_logs(hours=1)
    if not logs and not force:
        logger.info("✓ Son 1 saat içinde kaydedilen uyarı veya hata bulunamadı. Özet e-postası atlandı.")
        return True

    now_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    total_logs = len(logs)

    if total_logs > 0:
        table_html, unique_cats = build_summary_table(logs)
        status_banner = f"""
        <div style="background:rgba(245,158,11,0.15); border:1px solid #f59e0b; color:#fbbf24; padding:10px 16px; border-radius:8px; font-size:13px; font-weight:600; margin-bottom:16px;">
          ⚠️ Son 1 saatte {unique_cats} farklı kategoride toplam {total_logs} adet uyarı/hata kaydedildi.
        </div>
        """
    else:
        table_html = """
        <tr>
          <td colspan="5" style="text-align:center; padding:24px; color:#10b981; font-weight:600;">
            ✓ Son 1 saatte sistemde hiçbir hata veya uyarı kaydedilmedi. Tüm servisler stabil.
          </td>
        </tr>
        """
        status_banner = """
        <div style="background:rgba(16,185,129,0.15); border:1px solid #10b981; color:#34d399; padding:10px 16px; border-radius:8px; font-size:13px; font-weight:600; margin-bottom:16px;">
          ✓ Sistem Sağlıklı: Son 1 saatte 0 hata.
        </div>
        """

    subject = f"📊 [SAATLİK HATA ÖZETİ] MyTakip Sistem Raporu ({total_logs} Kayıt) - {now_str}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
      <meta charset="UTF-8">
      <title>Saatlik Sistem Raporu</title>
      <style>
        body {{ margin:0; padding:0; background:#080b12; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color:#f8fafc; }}
        .wrap {{ max-width:720px; margin:24px auto; background:#0f1422; border:1px solid rgba(255,255,255,0.08); border-radius:14px; overflow:hidden; }}
        .hdr {{ background:linear-gradient(135deg, #1e293b, #0f172a); padding:20px 24px; border-bottom:1px solid rgba(255,255,255,0.08); }}
        .hdr h1 {{ margin:0; font-size:20px; color:#ffffff; font-weight:700; }}
        .body {{ padding:24px 28px; }}
        table {{ width:100%; border-collapse:collapse; background:#161c2e; border-radius:8px; overflow:hidden; font-size:13px; }}
        th {{ background:rgba(255,255,255,0.04); padding:10px 12px; text-align:left; color:#94a3b8; font-size:11.5px; text-transform:uppercase; border-bottom:1px solid rgba(255,255,255,0.08); }}
        .footer {{ text-align:center; padding:16px 24px; font-size:12px; color:#64748b; border-top:1px solid rgba(255,255,255,0.06); }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="hdr">
          <h1>📊 MyTakip Saatlik Sistem Hata & Uyarı Özeti</h1>
          <div style="font-size:12px; color:#94a3b8; margin-top:4px;">Rapor Dönemi: Son 1 Saat · Oluşturulma: {now_str}</div>
        </div>
        <div class="body">
          {status_banner}
          <table>
            <thead>
              <tr>
                <th>Seviye</th>
                <th>Kategori</th>
                <th style="text-align:center;">Adet</th>
                <th>Zaman Aralığı</th>
                <th>Örnek Mesaj (Maskelenmiş)</th>
              </tr>
            </thead>
            <tbody>
              {table_html}
            </tbody>
          </table>
          <p style="font-size:12px; color:#64748b; margin-top:16px;">
            🔒 Tüm hassas bilgiler (şifre, PIN, token, api anahtarları) KVKK uyumlu maskelenmiştir.
          </p>
        </div>
        <div class="footer">
          MyTakip GitHub Actions Saatlik Otomasyonu (scripts/send_hourly_admin_summary.py)
        </div>
      </div>
    </body>
    </html>
    """

    if not RESEND_API_KEY:
        logger.info(f"ℹ️  RESEND_API_KEY ortam değişkeni tanımlı olmadığı için saatlik özet simülasyon modunda tamamlandı (Admin: {admin_email}).")
        return True

    success, msg = send_resend_email(admin_email, subject, html_content)
    if success and total_logs > 0:
        log_ids = [l.get('id') for l in logs if l.get('id')]
        mark_logs_as_notified(log_ids)

    return success


def main():
    parser = argparse.ArgumentParser(description="MyTakip Saatlik Admin Hata Özeti Gönderici")
    parser.add_argument('--force', action='store_true', help='Hata olmasa dahi saatlik sağlık e-postası gönderir')
    args = parser.parse_args()

    ok = send_hourly_summary(force=args.force)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
