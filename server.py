#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py - MyTakip Local Dev & Financial Markets API Server
Serves static files and proxies Borsa Istanbul (BIST), Gold, Currencies (USD/EUR/GBP),
and Cryptocurrencies (BTC/ETH/SOL/BNB/XRP) using 100% free, real-time public endpoints (TradingView).
"""

import http.server
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import urllib.request
import urllib.parse
import time
import os
import re

PORT = int(os.environ.get('PORT', 8765))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

CACHE = {}
CACHE_TTL = 15

SYMBOL_REGEX = re.compile(r'^[A-Z0-9_\.]{1,16}$')

class MyTakipHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def get_cors_origin(self):
        origin = self.headers.get('Origin', '')
        if origin:
            parsed = urllib.parse.urlparse(origin)
            if parsed.hostname in ('localhost', '127.0.0.1') or os.environ.get('PORT') or os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT'):
                return origin
        return f"http://localhost:{PORT}"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        clean_path = parsed.path

        if clean_path == '/api/quotes':
            params = urllib.parse.parse_qs(parsed.query)
            symbols_str = params.get('symbols', [''])[0].strip().upper()
            if not symbols_str:
                self.send_json({'error': 'symbols parametresi gereklidir'}, status=400)
                return
            raw_symbols = [s.strip() for s in symbols_str.split(',') if s.strip()]
            if len(raw_symbols) > 50:
                self.send_json({'error': 'En fazla 50 sembol sorgulanabilir'}, status=400)
                return
            symbols = [s for s in raw_symbols if SYMBOL_REGEX.match(s)]
            if not symbols:
                self.send_json({'error': 'Geçerli sembol bulunamadı. Yalnızca standart borsa sembolleri kabul edilir.'}, status=400)
                return
            data = self.fetch_batch_quotes(symbols)
            self.send_json(data)
            return

        if clean_path == '/api/quote':
            params = urllib.parse.parse_qs(parsed.query)
            symbol = params.get('symbol', [''])[0].strip().upper()

            if not symbol or not SYMBOL_REGEX.match(symbol):
                self.send_json({'error': 'Geçersiz veya eksik sembol parametresi. Yalnızca standart borsa sembolleri kabul edilir.'}, status=400)
                return

            data = self.fetch_market_data(symbol)
            self.send_json(data)
            return

        if self.path.startswith('/api/stocks'):
            stocks_file = os.path.join(DIRECTORY, 'bist_stocks.json')
            if os.path.exists(stocks_file):
                try:
                    with open(stocks_file, 'r', encoding='utf-8') as f:
                        stocks = json.load(f)
                    self.send_json(stocks)
                    return
                except Exception:
                    pass
            self.send_json([])
            return

        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', self.get_cors_origin())
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Vary', 'Origin')
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', self.get_cors_origin())
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def get_usd_try_rate(self):
        """Fetches current USD/TRY rate for converting USD assets (Gold, Crypto) to TRY"""
        now = time.time()
        cached = CACHE.get('FX_USDTRY')
        if cached and (now - cached['time'] < 60):
            return cached['data'].get('price', 50.0)

        usd_data = self.fetch_forex('USDTRY')
        rate = usd_data.get('price', 0)
        if rate > 0:
            return rate
        return 50.0

    def fetch_forex(self, pair):
        now = time.time()
        cache_key = f"FX_{pair}"
        if cache_key in CACHE and (now - CACHE[cache_key]['time'] < CACHE_TTL):
            return CACHE[cache_key]['data']

        url = 'https://scanner.tradingview.com/forex/scan'
        ticker = f"FX_IDC:{pair}"
        payload = json.dumps({
            'symbols': {'tickers': [ticker]},
            'columns': ['name', 'close', 'change', 'description']
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode('utf-8'))
                if d.get('data'):
                    row = d['data'][0]['d']
                    res = {
                        'symbol': pair.replace('TRY', ''),
                        'price': round(float(row[1]), 4),
                        'changePct': round(float(row[2]), 2) if row[2] is not None else 0,
                        'name': row[3] or pair,
                        'type': 'doviz',
                        'currency': 'TRY',
                        'source': 'TradingView'
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
        except Exception as e:
            print(f"[Forex Error {pair}]:", e)

        return {'symbol': pair, 'price': 0, 'error': 'fetch_failed'}

    def fetch_cfd_metal(self, ticker, sym_name):
        now = time.time()
        cache_key = f"CFD_{ticker}"
        if cache_key in CACHE and (now - CACHE[cache_key]['time'] < CACHE_TTL):
            return CACHE[cache_key]['data']

        url = 'https://scanner.tradingview.com/cfd/scan'
        payload = json.dumps({
            'symbols': {'tickers': [f"TVC:{ticker}"]},
            'columns': ['name', 'close', 'change', 'description']
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode('utf-8'))
                if d.get('data'):
                    row = d['data'][0]['d']
                    res = {
                        'symbol': ticker,
                        'usdPrice': round(float(row[1]), 2),
                        'changePct': round(float(row[2]), 2) if row[2] is not None else 0,
                        'name': row[3] or sym_name
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
        except Exception as e:
            print(f"[CFD Error {ticker}]:", e)

        return {'usdPrice': 0, 'changePct': 0}

    def fetch_crypto(self, std_sym, disp_name):
        now = time.time()
        cache_key = f"CRYPTO_{std_sym}"
        if cache_key in CACHE and (now - CACHE[cache_key]['time'] < CACHE_TTL):
            return CACHE[cache_key]['data']

        url = 'https://scanner.tradingview.com/crypto/scan'
        ticker = f"BINANCE:{std_sym}USDT"
        payload = json.dumps({
            'symbols': {'tickers': [ticker]},
            'columns': ['name', 'close', 'change', 'description']
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode('utf-8'))
                if d.get('data'):
                    row = d['data'][0]['d']
                    usd_val = float(row[1])
                    usd_try = self.get_usd_try_rate()
                    try_val = round(usd_val * usd_try, 2)
                    res = {
                        'symbol': std_sym,
                        'name': disp_name,
                        'price': try_val,
                        'usdPrice': round(usd_val, 2),
                        'changePct': round(float(row[2]), 2) if row[2] is not None else 0,
                        'type': 'kripto',
                        'currency': 'TRY',
                        'source': 'TradingView (Binance)'
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
        except Exception as e:
            print(f"[Crypto Error {std_sym}]:", e)

        return {'symbol': std_sym, 'price': 0, 'error': 'fetch_failed'}

    def fetch_market_data(self, raw_symbol):
        symbol = raw_symbol.upper().replace(' ', '_').strip()
        now = time.time()

        if symbol in CACHE and (now - CACHE[symbol]['time'] < CACHE_TTL):
            return CACHE[symbol]['data']

        if symbol in ['USD', 'DOLAR', 'USD_TRY', 'USDTRY', 'USDTRY=X']:
            res = self.fetch_forex('USDTRY')
            res['symbol'] = 'USD'
            res['name'] = 'Amerikan Doları (USD)'
            return res

        if symbol in ['EUR', 'EURO', 'EUR_TRY', 'EURTRY', 'EURTRY=X']:
            res = self.fetch_forex('EURTRY')
            res['symbol'] = 'EUR'
            res['name'] = 'Euro (EUR)'
            return res

        if symbol in ['GBP', 'STERLIN', 'GBP_TRY', 'GBPTRY', 'GBPTRY=X']:
            res = self.fetch_forex('GBPTRY')
            res['symbol'] = 'GBP'
            res['name'] = 'İngiliz Sterlini (GBP)'
            return res

        crypto_map = {
            'BTC': 'Bitcoin (BTC)',
            'BITCOIN': 'Bitcoin (BTC)',
            'ETH': 'Ethereum (ETH)',
            'ETHEREUM': 'Ethereum (ETH)',
            'SOL': 'Solana (SOL)',
            'SOLANA': 'Solana (SOL)',
            'BNB': 'Binance Coin (BNB)',
            'BINANCE_COIN': 'Binance Coin (BNB)',
            'XRP': 'Ripple (XRP)',
            'RIPPLE': 'Ripple (XRP)'
        }
        if symbol in crypto_map:
            std_sym = 'BTC' if 'BTC' in symbol else ('ETH' if 'ETH' in symbol else ('SOL' if 'SOL' in symbol else ('BNB' if 'BNB' in symbol else 'XRP')))
            return self.fetch_crypto(std_sym, crypto_map[symbol])

        if symbol in ['GRAM_ALTIN', 'ALTIN', 'GRAM', 'XAU_TRY']:
            gold_res = self.fetch_cfd_metal('GOLD', 'Gold Spot')
            ons_usd = gold_res.get('usdPrice', 0)
            usd_try = self.get_usd_try_rate()
            if ons_usd > 0 and usd_try > 0:
                gram_tl = round((ons_usd / 31.1034768) * usd_try, 2)
                res = {
                    'symbol': 'GRAM_ALTIN',
                    'name': 'Gram Altın (24 Ayar)',
                    'price': gram_tl,
                    'usdPrice': ons_usd,
                    'currency': 'TRY',
                    'changePct': gold_res.get('changePct', 0),
                    'type': 'altin',
                    'source': 'TradingView (Calculated)'
                }
                CACHE[symbol] = {'data': res, 'time': now}
                return res
            return {'symbol': 'GRAM_ALTIN', 'name': 'Gram Altın (24 Ayar)', 'price': 6500.0, 'currency': 'TRY', 'changePct': 0, 'type': 'altin'}

        if symbol in ['CEYREK_ALTIN', 'CEYREK']:
            gram = self.fetch_market_data('GRAM_ALTIN')
            gram_price = gram.get('price', 6500.0)
            ceyrek_price = round(gram_price * 1.635 * 1.025, 2)
            res = {
                'symbol': 'CEYREK_ALTIN',
                'name': 'Çeyrek Altın (Darphane)',
                'price': ceyrek_price,
                'currency': 'TRY',
                'changePct': gram.get('changePct', 0),
                'type': 'altin',
                'source': 'Calculated'
            }
            CACHE[symbol] = {'data': res, 'time': now}
            return res

        if symbol in ['GUMUS', 'GRAM_GUMUS', 'XAG_TRY']:
            silver_res = self.fetch_cfd_metal('SILVER', 'Silver Spot')
            ons_usd = silver_res.get('usdPrice', 0)
            usd_try = self.get_usd_try_rate()
            if ons_usd > 0 and usd_try > 0:
                gumus_tl = round((ons_usd / 31.1034768) * usd_try, 2)
                res = {
                    'symbol': 'GUMUS',
                    'name': 'Gram Gümüş (999 Ayar)',
                    'price': gumus_tl,
                    'currency': 'TRY',
                    'changePct': silver_res.get('changePct', 0),
                    'type': 'altin',
                    'source': 'TradingView (Calculated)'
                }
                CACHE[symbol] = {'data': res, 'time': now}
                return res

        clean_sym = symbol.replace('.IS', '').replace('BIST:', '').strip()
        url = 'https://scanner.tradingview.com/turkey/scan'
        payload = json.dumps({
            'symbols': {'tickers': [f"BIST:{clean_sym}"]},
            'columns': ['name', 'close', 'change', 'change_abs', 'description']
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode('utf-8'))
                if d.get('data'):
                    row = d['data'][0]['d']
                    price = round(float(row[1]), 2) if row[1] is not None else 0
                    chg_pct = round(float(row[2]), 2) if row[2] is not None else 0
                    chg_abs = round(float(row[3]), 2) if row[3] is not None else 0
                    comp_name = row[4] or clean_sym
                    res = {
                        'symbol': clean_sym,
                        'name': comp_name,
                        'price': price,
                        'change': chg_abs,
                        'changePct': chg_pct,
                        'currency': 'TRY',
                        'type': 'hisse',
                        'source': 'Borsa Istanbul (TradingView Live)',
                        'updatedAt': int(time.time())
                    }
                    CACHE[symbol] = {'data': res, 'time': now}
                    return res
        except Exception as e:
            print(f"[BIST Error {clean_sym}]:", e)

        return {
            'symbol': clean_sym,
            'name': clean_sym,
            'price': 0,
            'error': 'Fiyat verisi bulunamadı',
            'source': 'N/A'
        }

    def fetch_batch_quotes(self, symbols):
        """Fetches multiple symbols efficiently in batch"""
        results = {}
        bist_symbols = []

        for s in symbols:
            s_clean = s.strip().upper()
            if s_clean in ['USD', 'DOLAR', 'EUR', 'EURO', 'GBP', 'STERLIN', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'GRAM_ALTIN', 'ALTIN', 'CEYREK_ALTIN', 'GUMUS']:
                results[s_clean] = self.fetch_market_data(s_clean)
            else:
                bist_sym = s_clean.replace('.IS', '').replace('BIST:', '').strip()
                bist_symbols.append(bist_sym)

        if bist_symbols:
            tickers = [f"BIST:{sym}" for sym in bist_symbols]
            url = 'https://scanner.tradingview.com/turkey/scan'
            payload = json.dumps({
                'symbols': {'tickers': tickers},
                'columns': ['name', 'close', 'change', 'change_abs', 'description']
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=7) as r:
                    d = json.loads(r.read().decode('utf-8'))
                    for row in d.get('data', []):
                        vals = row['d']
                        sym = vals[0]
                        price = round(float(vals[1]), 2) if vals[1] is not None else 0
                        chg_pct = round(float(vals[2]), 2) if vals[2] is not None else 0
                        chg_abs = round(float(vals[3]), 2) if vals[3] is not None else 0
                        comp_name = vals[4] or sym
                        item_data = {
                            'symbol': sym,
                            'name': comp_name,
                            'price': price,
                            'change': chg_abs,
                            'changePct': chg_pct,
                            'currency': 'TRY',
                            'type': 'hisse',
                            'source': 'Borsa Istanbul (TradingView Live)',
                            'updatedAt': int(time.time())
                        }
                        results[sym] = item_data
                        CACHE[sym] = {'data': item_data, 'time': time.time()}
            except Exception as e:
                print("[Batch BIST Error]:", e)

        for s in symbols:
            s_clean = s.strip().upper().replace('.IS', '').replace('BIST:', '')
            if s_clean not in results:
                results[s_clean] = self.fetch_market_data(s_clean)

        return results

handler = MyTakipHandler
app = MyTakipHandler
application = MyTakipHandler

if __name__ == '__main__':
    with ThreadingHTTPServer(('', PORT), MyTakipHandler) as httpd:
        print(f"MyTakip Threaded Server & BIST (All 650+ Stocks)/Forex/Crypto API running at http://localhost:{PORT}")
        httpd.serve_forever()
