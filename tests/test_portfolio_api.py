#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_portfolio_api.py
Bağımsız Portföy API Test Betiği

Kullanım:
  Belirli bir varlık için:
    python3 test_portfolio_api.py ATATP
    python3 test_portfolio_api.py THYAO
    python3 test_portfolio_api.py USD
    python3 test_portfolio_api.py GRAM_ALTIN
    python3 test_portfolio_api.py BTC

  Tüm ana varlık sınıflarını toplu test etmek için:
    python3 test_portfolio_api.py
"""

import os
import sys
import time
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ROOT_DIR) if os.path.basename(ROOT_DIR) == 'tests' else ROOT_DIR
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.isdir(BACKEND_DIR) and BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from portfolio_engine import fetch_market_data

def format_currency(val, symbol='TRY'):
    if symbol == 'TRY':
        return f"{val:,.2f} ₺".replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"${val:,.2f}"

def test_symbol(symbol):
    print("=" * 72)
    print(f"📊 PORTFÖY PİYASA VERİSİ SORGULANIYOR: {symbol.upper()}")
    print("=" * 72)

    start_time = time.time()
    try:
        data = fetch_market_data(symbol, force_refresh=True)
    except Exception as e:
        print(f"❌ Beklenmeyen Hata: {e}")
        return False

    elapsed_ms = int((time.time() - start_time) * 1000)
    price = data.get('price', 0)
    success = data.get('success', False) and (price > 0)
    chg_pct = data.get('changePct', 0)
    chg_sign = "+" if chg_pct > 0 else ""
    now_str = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

    print(f"  • Varlık Sembolü : {data.get('symbol', symbol)}")
    print(f"  • Varlık Adı     : {data.get('name', 'N/A')}")
    print(f"  • Varlık Türü    : {data.get('type', 'N/A')}")
    print(f"  • Güncel Fiyat   : {format_currency(price, 'TRY')} (Sayısal: {price})")
    if 'usdPrice' in data and data['usdPrice']:
        print(f"  • USD Fiyatı     : ${data['usdPrice']:,.2f}")
    print(f"  • Günlük Değişim : {chg_sign}{chg_pct:.2f}%")
    print(f"  • Veri Kaynağı   : {data.get('source', 'Bilinmiyor')}")
    print(f"  • Sorgu Süresi   : {elapsed_ms} ms")
    print(f"  • Zaman Damgası  : {now_str}")

    if success:
        print(f"\n  ✅ SONUÇ: [BAŞARILI - SUCCESS] (Fiyat başarıyla çekildi)")
    else:
        err_msg = data.get('error', 'Fiyat verisi 0 döndü veya alınamadı.')
        print(f"\n  ❌ SONUÇ: [BAŞARISIZ - FAILED]")
        print(f"  ⚠️  Hata Detayı: {err_msg}")

    print("=" * 72 + "\n")
    return success

def main():
    if len(sys.argv) > 1:
        target_symbols = [s.strip().upper() for s in sys.argv[1:] if s.strip()]
    else:
        # Varsayılan test paketi (Hisse, Döviz, Altın, Kripto)
        target_symbols = ['ATATP', 'THYAO', 'USD', 'GRAM_ALTIN', 'BTC']

    print("\n" + "#" * 72)
    print("🚀 MYTAKIP PORTFÖY PİYASA VERİSİ API BAĞLANTI TESTİ")
    print(f"🕒 Başlangıç: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"📋 Test Edilecek Varlıklar: {', '.join(target_symbols)}")
    print("#" * 72 + "\n")

    all_passed = True
    results = {}

    for sym in target_symbols:
        passed = test_symbol(sym)
        results[sym] = passed
        if not passed:
            all_passed = False

    print("#" * 72)
    print("📈 TEST ÖZET RAPORU:")
    for sym, status in results.items():
        icon = "✅ BAŞARILI" if status else "❌ BAŞARISIZ"
        print(f"  - {sym.ljust(12)}: {icon}")
    print("#" * 72 + "\n")

    if not all_passed:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
