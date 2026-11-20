#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/test_portfolio_pnl.py
========================================================================
MyTakip Yatırım & Portföy Kâr/Zarar (P&L) Motoru Uçtan Uca Doğrulama Testi
========================================================================
Test Kapsamı:
1. Çoklu Alış ve Ağırlıklı Ortalama Maliyet (WAC - Weighted Average Cost) Doğrulaması.
2. Kısmi Satış (Realized P&L İzolasyonu) ve Sonrasında Fiyat Düşüş / Artış Senaryoları.
3. Tam Satış (Miktar = 0, Aktif Portföyden & K/Z'den Dışlanma ve Değişmez Ledger Koruması).
4. Eksik/Hatalı Canlı Fiyat Yönetimi (Sessiz fallback olmaması, 0 Bakiye Bozulması ve NaN Koruması).
5. Kur Normalizasyonu (USD/TRY) ve Yüksek Hassasiyetli Ondalık / Toz Miktar (Dust <= 1e-8) Koruması.
"""

import sys
import os
import unittest
from decimal import Decimal

# Proje kök dizinini ve backend dizinini sys.path'e ekle
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import portfolio_engine as pe

class TestPortfolioPnLEngine(unittest.TestCase):

    def setUp(self):
        self.usd_rate = Decimal('35.0')

    def test_scenario_1_multiple_buys_weighted_average_cost(self):
        """
        Senaryo 1: Farklı fiyatlardan çoklu alım ve Ağırlıklı Ortalama Maliyet (WAC) doğrulaması.
        - Alış 1: 10 THYAO @ 100 TL -> Maliyet: 1.000 TL, Ortalama: 100 TL
        - Alış 2: 20 THYAO @ 160 TL -> Yeni Maliyet: 1.000 + 3.200 = 4.200 TL, Adet: 30, Ortalama: 140 TL
        - Alış 3: 10 THYAO @ 200 TL -> Yeni Maliyet: 4.200 + 2.000 = 6.200 TL, Adet: 40, Ortalama: 155 TL
        - Canlı Fiyat: 180 TL
        - Güncel Değer: 40 * 180 = 7.200 TL
        - Gerçekleşmemiş K/Z: 7.200 - 6.200 = +1.000 TL (+%16.13)
        """
        trades = [
            {'id': 1, 'symbol': 'THYAO', 'name': 'Türk Hava Yolları', 'type': 'alis', 'qty': 10, 'price': 100.0, 'date': '2026-01-01', 'createdAt': 1000},
            {'id': 2, 'symbol': 'THYAO', 'name': 'Türk Hava Yolları', 'type': 'alis', 'qty': 20, 'price': 160.0, 'date': '2026-01-02', 'createdAt': 2000},
            {'id': 3, 'symbol': 'THYAO', 'name': 'Türk Hava Yolları', 'type': 'alis', 'qty': 10, 'price': 200.0, 'date': '2026-01-03', 'createdAt': 3000},
        ]

        pos = pe.calculate_asset_position(
            symbol='THYAO',
            transactions=trades,
            live_price_data={'price': 180.0, 'currency': 'TRY', 'success': True}
        )

        self.assertTrue(pos['is_active'], "Pozisyon aktif olmalıdır")
        self.assertEqual(pos['quantity'], 40.0, "Toplam miktar 40 olmalıdır")
        self.assertEqual(pos['avg_cost'], 155.0, "WAC ortalama maliyeti tam 155.00 TL olmalıdır")
        self.assertEqual(pos['cost_basis'], 6200.0, "Toplam maliyet tabanı 6.200.00 TL olmalıdır")
        self.assertEqual(pos['current_value'], 7200.0, "Güncel değer 7.200.00 TL olmalıdır")
        self.assertEqual(pos['unrealized_pnl'], 1000.0, "Kâr tam +1.000.00 TL olmalıdır")
        self.assertAlmostEqual(pos['unrealized_pnl_percent'], 16.13, places=2, msg="K/Z yüzdesi %16.13 olmalıdır")
        self.assertFalse(pos['price_unavailable'], "Fiyat geçerli olmalıdır")
        self.assertEqual(pos['total_realized_pnl'], 0.0, "Henüz satış olmadığı için realize edilmiş kâr 0 olmalıdır")

    def test_scenario_2_partial_sell_and_price_fluctuations(self):
        """
        Senaryo 2: Kısmi satış ve fiyat dalgalanmaları (Düşüş / Artış).
        - Senaryo 1'in devamı (40 adet @ 155 TL maliyet, toplam 6.200 TL).
        - Satış: 15 THYAO @ 190 TL
          * Ortalama maliyet DEĞİŞMEZ (155 TL).
          * Kalan miktar: 40 - 15 = 25 adet.
          * Kalan maliyet tabanı: 25 * 155 = 3.875 TL.
          * Realize Edilen Kâr: (190 - 155) * 15 = +525 TL.
          * Realize kâr, aktif pozisyonun maliyet tabanına ASLA karıştırılmaz.
        - Fiyat Düşüşü: Canlı fiyat 140 TL'ye düşerse:
          * Güncel Değer: 25 * 140 = 3.500 TL
          * Gerçekleşmemiş K/Z: 3.500 - 3.875 = -375 TL (-%9.68 zarar)
        - Fiyat Artışı: Canlı fiyat 210 TL'ye çıkarsa:
          * Güncel Değer: 25 * 210 = 5.250 TL
          * Gerçekleşmemiş K/Z: 5.250 - 3.875 = +1.375 TL (+%35.48 kâr)
          * Realize Edilen Kâr hala +525 TL olarak bağımsız korunur.
        """
        trades = [
            {'id': 1, 'symbol': 'THYAO', 'type': 'alis', 'qty': 10, 'price': 100.0, 'date': '2026-01-01', 'createdAt': 1000},
            {'id': 2, 'symbol': 'THYAO', 'type': 'alis', 'qty': 20, 'price': 160.0, 'date': '2026-01-02', 'createdAt': 2000},
            {'id': 3, 'symbol': 'THYAO', 'type': 'alis', 'qty': 10, 'price': 200.0, 'date': '2026-01-03', 'createdAt': 3000},
            {'id': 4, 'symbol': 'THYAO', 'type': 'satis', 'qty': 15, 'price': 190.0, 'date': '2026-01-04', 'createdAt': 4000},
        ]

        # 1. Fiyat Düşüş Durumu (140 TL)
        pos_drop = pe.calculate_asset_position(
            symbol='THYAO',
            transactions=trades,
            live_price_data={'price': 140.0, 'currency': 'TRY', 'success': True}
        )

        self.assertEqual(pos_drop['quantity'], 25.0, "Kalan miktar 25 olmalıdır")
        self.assertEqual(pos_drop['avg_cost'], 155.0, "Satış sonrası birim maliyet DEĞİŞMEMELİDİR (155 TL)")
        self.assertEqual(pos_drop['cost_basis'], 3875.0, "Maliyet tabanı orantılı olarak 3.875 TL'ye düşmelidir")
        self.assertEqual(pos_drop['total_realized_pnl'], 525.0, "Realize edilen kâr (190-155)*15 = +525 TL olmalıdır")
        self.assertEqual(pos_drop['current_value'], 3500.0, "Düşüşte güncel değer 3.500 TL olmalıdır")
        self.assertEqual(pos_drop['unrealized_pnl'], -375.0, "Zarar -375 TL olmalıdır")
        self.assertAlmostEqual(pos_drop['unrealized_pnl_percent'], -9.68, places=2)

        # 2. Fiyat Artış Durumu (210 TL)
        pos_rise = pe.calculate_asset_position(
            symbol='THYAO',
            transactions=trades,
            live_price_data={'price': 210.0, 'currency': 'TRY', 'success': True}
        )

        self.assertEqual(pos_rise['current_value'], 5250.0, "Artışta güncel değer 5.250 TL olmalıdır")
        self.assertEqual(pos_rise['unrealized_pnl'], 1375.0, "Artışta kâr 5.250 - 3.875 = +1.375 TL olmalıdır")
        self.assertAlmostEqual(pos_rise['unrealized_pnl_percent'], 35.48, places=2)
        self.assertEqual(pos_rise['total_realized_pnl'], 525.0, "Realize edilen kâr etkilenmeden +525 TL kalmalıdır")

    def test_scenario_3_full_sell_and_active_portfolio_exclusion(self):
        """
        Senaryo 3: Tam satış (Full Sell) ve Aktif Portföyden İzolasyon.
        - Kalan 25 THYAO'nun tamamı 210 TL'den satılır.
        - Kalan miktar tam 0 olmalıdır (is_active = False).
        - Aktif maliyet tabanı ve gerçekleşmemiş K/Z 0 olmalıdır.
        - İkinci satıştan realize edilen kâr: (210 - 155) * 25 = +1.375 TL.
        - Toplam realize edilen kâr: 525 + 1.375 = +1.900 TL.
        - Genel portföy özeti (portfolio_pnl) hesaplandığında, THYAO aktif pozisyonlardan
          tamamen dışlanmalı ve aktif toplamları etkilememelidir.
        - 5 adet işlem geçmişi (ledger) kesinlikle silinmeden (değişmezlik) korunmalıdır.
        """
        trades = [
            {'id': 1, 'symbol': 'THYAO', 'type': 'alis', 'qty': 10, 'price': 100.0, 'date': '2026-01-01', 'createdAt': 1000},
            {'id': 2, 'symbol': 'THYAO', 'type': 'alis', 'qty': 20, 'price': 160.0, 'date': '2026-01-02', 'createdAt': 2000},
            {'id': 3, 'symbol': 'THYAO', 'type': 'alis', 'qty': 10, 'price': 200.0, 'date': '2026-01-03', 'createdAt': 3000},
            {'id': 4, 'symbol': 'THYAO', 'type': 'satis', 'qty': 15, 'price': 190.0, 'date': '2026-01-04', 'createdAt': 4000},
            {'id': 5, 'symbol': 'THYAO', 'type': 'satis', 'qty': 25, 'price': 210.0, 'date': '2026-01-05', 'createdAt': 5000},
        ]

        pos_closed = pe.calculate_asset_position(
            symbol='THYAO',
            transactions=trades,
            live_price_data={'price': 210.0, 'currency': 'TRY', 'success': True}
        )

        self.assertFalse(pos_closed['is_active'], "Pozisyon kapanmış olmalı (is_active = False)")
        self.assertEqual(pos_closed['quantity'], 0.0, "Kalan adet tam 0 olmalıdır")
        self.assertEqual(pos_closed['cost_basis'], 0.0, "Kapalı pozisyon maliyet tabanı 0 olmalıdır")
        self.assertEqual(pos_closed['current_value'], 0.0, "Kapalı pozisyon güncel değeri 0 olmalıdır")
        self.assertEqual(pos_closed['unrealized_pnl'], 0.0, "Kapalı pozisyon aktif k/z üretmemelidir")
        self.assertEqual(pos_closed['total_realized_pnl'], 1900.0, "Kümülatif realize edilen kâr 1.900 TL olmalıdır")
        self.assertEqual(pos_closed['trades_count'], 5, "5 işlemin tamamı ledgerda korunmalıdır")

        # Portföy genel özetini test et: Başka açık pozisyon (örn. SASA) ekle
        trades.append({'id': 6, 'symbol': 'SASA', 'type': 'alis', 'qty': 100, 'price': 50.0, 'date': '2026-01-06'})
        pnl_result = pe.calculate_portfolio_pnl(
            transactions=trades,
            market_quotes={
                'THYAO': {'price': 210.0, 'currency': 'TRY', 'success': True},
                'SASA': {'price': 60.0, 'currency': 'TRY', 'success': True}
            }
        )

        active_symbols = [p['symbol'] for p in pnl_result['positions']]
        self.assertNotIn('THYAO', active_symbols, "Tamamı satılan THYAO aktif portföy listesinde yer almamalıdır")
        self.assertIn('SASA', active_symbols, "Açık pozisyon olan SASA aktif portföyde yer almalıdır")

        summary = pnl_result['summary']
        self.assertEqual(summary['total_cost'], 5000.0, "Aktif toplam maliyet sadece SASA'ya (5.000 TL) eşit olmalıdır")
        self.assertEqual(summary['total_current_value'], 6000.0, "Aktif güncel değer 6.000 TL olmalıdır")
        self.assertEqual(summary['total_unrealized_pnl'], 1000.0, "Aktif kâr +1.000 TL olmalıdır")
        self.assertEqual(summary['total_realized_pnl'], 1900.0, "THYAO'dan elde edilen realize kâr özette korunmalıdır")

    def test_scenario_4_missing_or_failed_live_price_handling(self):
        """
        Senaryo 4: Eksik veya Başarısız Canlı Fiyat Yönetimi.
        - Alış: 2 BTC @ 1.500.000 TL (Maliyet: 3.000.000 TL).
        - Canlı fiyat API'si başarısız olur (None, 0 veya success: False).
        - KRİTİK DENETİMLER:
          1. Sessizce maliyet fiyatına (avgCost) EŞİTLENMEMELİDİR (Bu durum sahte 0 TL / %0 K/Z üretirdi).
          2. Güncel değer 0'a SIFIRLANMAMALIDIR (Bu durum tüm portföyü sıfırlar ve sahte -%100 zarar gösterirdi).
          3. price_unavailable = True bayrağı set edilmeli, current_value ve unrealized_pnl None olmalıdır.
          4. Bölme sıfır (Infinity) veya NaN çökmeleri %100 engellenmelidir.
          5. Genel portföy toplamı 0 TL'ye düşürülmemelidir.
        """
        trades = [
            {'id': 1, 'symbol': 'BTC', 'type': 'alis', 'qty': 2, 'price': 1500000.0, 'date': '2026-01-01'}
        ]

        # Başarısız API yanıtı simülasyonu
        pos_failed = pe.calculate_asset_position(
            symbol='BTC',
            transactions=trades,
            live_price_data={'price': 0, 'success': False, 'error': 'API Timeout'}
        )

        self.assertTrue(pos_failed['price_unavailable'], "Fiyat alınamadığında price_unavailable True olmalıdır")
        self.assertIsNone(pos_failed['live_price'], "Canlı fiyat None olmalı, avgCost ile maskelenmemelidir")
        self.assertIsNone(pos_failed['current_value'], "Güncel değer 0 TL'ye sıfırlanmamalı, None olmalıdır")
        self.assertIsNone(pos_failed['unrealized_pnl'], "K/Z 0 TL yerine None olarak işaretlenmelidir")
        self.assertIsNone(pos_failed['unrealized_pnl_percent'], "K/Z yüzdesi %0.00 yerine None olmalıdır")
        self.assertEqual(pos_failed['cost_basis'], 3000000.0, "Maliyet tabanı bozulmadan 3.000.000 TL kalmalıdır")

        # Portföy genel özetinde sıfırlanmama kontrolü
        pnl_result = pe.calculate_portfolio_pnl(
            transactions=trades,
            market_quotes={'BTC': {'price': 0, 'success': False}}
        )

        summary = pnl_result['summary']
        self.assertTrue(summary['has_unpriced_assets'], "Fiyatı eksik varlık varlığı bayrağı aktifleşmelidir")
        self.assertEqual(summary['unpriced_assets_count'], 1)
        self.assertEqual(summary['total_cost'], 3000000.0, "Maliyet toplamı korunmalıdır")
        self.assertIsNone(summary['total_current_value'], "Tüm fiyatlar eksikken güncel değer 0 yapılmamalıdır")
        self.assertIsNone(summary['total_unrealized_pnl'], "Tüm fiyatlar eksikken K/Z 0 yapılmamalıdır")

    def test_scenario_5_currency_normalization_and_precision_dust(self):
        """
        Senaryo 5: Döviz Normalizasyonu (USD -> TRY) ve Toz Miktar (Dust <= 1e-8) Koruması.
        - Alış: 0.5 BTC @ 60.000 USD, Alış tarihindeki kur: 35.0 TL.
          * TRY Maliyet: 60.000 * 35.0 = 2.100.000 TL birim fiyat.
          * Toplam Maliyet: 0.5 * 2.100.000 = 1.050.000 TL.
        - Canlı Fiyat: 70.000 USD, Güncel kur: 36.0 TL.
          * Güncel TRY Fiyatı: 70.000 * 36.0 = 2.520.000 TL.
          * Güncel Değer: 0.5 * 2.520.000 = 1.260.000 TL.
          * Kâr: 1.260.000 - 1.050.000 = +210.000 TL (+%20.00).
        - Toz Miktar (Epsilon): 0.499999999 BTC satıldığında geriye 1e-9 BTC kalır.
          * Epsilon kuralı (<= 1e-8) gereği bu miktar otomatik 0 kabul edilmeli ve pozisyon kapanmalıdır.
        """
        trades = [
            {
                'id': 1,
                'symbol': 'BTC',
                'type': 'alis',
                'qty': 0.5,
                'price': 60000.0,
                'currency': 'USD',
                'usd_try_rate': 35.0,
                'date': '2026-01-01'
            }
        ]

        pos_crypto = pe.calculate_asset_position(
            symbol='BTC',
            transactions=trades,
            live_price_data={'price': 70000.0, 'currency': 'USD', 'success': True},
            live_usd_try_rate=Decimal('36.0')
        )

        self.assertEqual(pos_crypto['cost_basis'], 1050000.0, "Maliyet tabanı tam 1.050.000 TL olmalıdır")
        self.assertEqual(pos_crypto['current_value'], 1260000.0, "Güncel değer tam 1.260.000 TL olmalıdır")
        self.assertEqual(pos_crypto['unrealized_pnl'], 210000.0, "Kâr tam +210.000 TL olmalıdır")
        self.assertAlmostEqual(pos_crypto['unrealized_pnl_percent'], 20.0, places=2)

        # Toz miktar (dust) testi: 0.4999999999 satılır
        trades.append({
            'id': 2,
            'symbol': 'BTC',
            'type': 'satis',
            'qty': 0.4999999999,
            'price': 70000.0,
            'currency': 'USD',
            'usd_try_rate': 36.0,
            'date': '2026-01-02'
        })

        pos_dust = pe.calculate_asset_position(
            symbol='BTC',
            transactions=trades,
            live_price_data={'price': 70000.0, 'currency': 'USD', 'success': True},
            live_usd_try_rate=Decimal('36.0')
        )

        self.assertEqual(pos_dust['quantity'], 0.0, "1e-8 altındaki toz miktar tam 0'a yuvarlanmalıdır")
        self.assertFalse(pos_dust['is_active'], "Toz bakiye kalan pozisyon pasif olmalıdır")
        self.assertEqual(pos_dust['cost_basis'], 0.0)

    def test_scenario_6_number_formatting_and_zero_division_guard(self):
        """
        Senaryo 6: Sayı ve Para Formatlaması ile Sıfıra Bölme Koruması.
        - format_currency fonksiyonu binlik ayraçlı virgül ve iki basamak üretmelidir (12,450.75 TL).
        - Boş pozisyonda veya 0 maliyette K/Z yüzdesi hesaplanırken division by zero koruması.
        """
        self.assertEqual(pe.format_currency(12450.75, 'TL'), '12,450.75 TL')
        self.assertEqual(pe.format_currency(1000000, 'TL'), '1,000,000.00 TL')
        self.assertEqual(pe.format_currency(None), '—')

        # 0 maliyet koruması
        trades = [{'id': 1, 'symbol': 'TEST', 'type': 'alis', 'qty': 0, 'price': 0}]
        pos = pe.calculate_asset_position('TEST', trades, live_price_data=100.0)
        self.assertEqual(pos['quantity'], 0.0)
        self.assertEqual(pos['unrealized_pnl_percent'], 0.0)

def run_tests():
    print("\n" + "=" * 76)
    print("🚀 MYTAKIP YATIRIM & PORTFÖY P&L MOTORU DOĞRULAMA TEST PROTOKOLÜ 🚀")
    print("=" * 76 + "\n")

    suite = unittest.TestLoader().loadTestsFromTestCase(TestPortfolioPnLEngine)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 76)
    if result.wasSuccessful():
        print("🎉 TÜM PORTFÖY VE P&L HESAPLAMA TESTLERİ %100 BAŞARIYLA GEÇTİ! 🚀")
        print("=" * 76 + "\n")
        return 0
    else:
        print("❌ BAZI TESTLER BAŞARISIZ OLDU!")
        print("=" * 76 + "\n")
        return 1

if __name__ == '__main__':
    sys.exit(run_tests())
