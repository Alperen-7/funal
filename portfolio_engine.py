#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portfolio_engine.py
Sağlam, çok kaynaklı (Dual-Provider: TradingView & Yahoo Finance) portföy piyasa verisi motoru.
Hisse (BIST), Döviz, Altın/Gümüş ve Kripto varlıklar için yüksek erişilebilirlik ve hata loglaması sunar.
"""

import json
import logging
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
import warnings

# macOS LibreSSL uyarılarını bastır
warnings.filterwarnings('ignore', message='.*urllib3 v2 only supports OpenSSL.*')
warnings.filterwarnings('ignore', category=UserWarning)

try:
    import scripts.admin_logger as admin_logger
except ImportError:
    try:
        import admin_logger
    except ImportError:
        admin_logger = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [PortfolioAPI] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('portfolio_engine')

CACHE = {}
CACHE_TTL = 30

HTTP_HEADERS_TV = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json'
}

HTTP_HEADERS_YAHOO = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_bist_symbol(raw_symbol):
    if not raw_symbol:
        return ''
    return raw_symbol.upper().replace('.IS', '').replace('BIST:', '').replace(' ', '_').strip()

def get_usd_try_rate(force_refresh=False):
    now = time.time()
    cache_key = 'FX_USDTRY_RATE'
    if not force_refresh and cache_key in CACHE and (now - CACHE[cache_key]['time'] < 60):
        return CACHE[cache_key]['data']

    usd_data = fetch_forex('USDTRY', force_refresh=force_refresh)
    rate = usd_data.get('price', 0)
    if rate > 0:
        CACHE[cache_key] = {'data': rate, 'time': now}
        return rate
    return 35.0

def fetch_forex(pair, force_refresh=False):
    pair_clean = pair.upper().strip()
    cache_key = f"FX_{pair_clean}"
    now = time.time()
    if not force_refresh and cache_key in CACHE and (now - CACHE[cache_key]['time'] < CACHE_TTL):
        return CACHE[cache_key]['data']

    # 1. TradingView Forex Scan
    tv_url = 'https://scanner.tradingview.com/forex/scan'
    ticker = f"FX_IDC:{pair_clean}"
    payload = json.dumps({
        'symbols': {'tickers': [ticker]},
        'columns': ['name', 'close', 'change', 'description']
    }).encode('utf-8')
    try:
        req = urllib.request.Request(tv_url, data=payload, headers=HTTP_HEADERS_TV)
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode('utf-8'))
            if d.get('data'):
                row = d['data'][0]['d']
                price = round(float(row[1]), 4) if row[1] is not None else 0
                if price > 0:
                    res = {
                        'symbol': pair_clean.replace('TRY', ''),
                        'price': price,
                        'changePct': round(float(row[2]), 2) if row[2] is not None else 0,
                        'name': row[3] or pair_clean,
                        'type': 'doviz',
                        'currency': 'TRY',
                        'source': 'TradingView (Forex Live)',
                        'updatedAt': int(time.time()),
                        'success': True
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
    except Exception as e:
        logger.warning(f"TradingView Forex scan failed for {pair_clean}: {e}. Trying Yahoo Finance...")

    # 2. Yahoo Finance Fallback
    try:
        yf_symbol = f"{pair_clean}=X"
        yf_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}?interval=1d&range=1d"
        req = urllib.request.Request(yf_url, headers=HTTP_HEADERS_YAHOO)
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode('utf-8'))
            results = d.get('chart', {}).get('result', [])
            if results:
                meta = results[0].get('meta', {})
                price = meta.get('regularMarketPrice')
                prev = meta.get('chartPreviousClose') or meta.get('previousClose')
                if price and float(price) > 0:
                    price_val = round(float(price), 4)
                    chg_pct = round(((price_val - prev) / prev) * 100, 2) if (prev and prev > 0) else 0.0
                    res = {
                        'symbol': pair_clean.replace('TRY', ''),
                        'price': price_val,
                        'changePct': chg_pct,
                        'name': meta.get('shortName') or pair_clean,
                        'type': 'doviz',
                        'currency': 'TRY',
                        'source': 'Yahoo Finance (Forex Live)',
                        'updatedAt': int(time.time()),
                        'success': True
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
    except Exception as e:
        logger.error(f"Yahoo Finance Forex failed for {pair_clean}: {e}")

    return {
        'symbol': pair_clean.replace('TRY', ''),
        'price': 0,
        'error': f'Döviz kuru alınamadı ({pair_clean})',
        'success': False,
        'source': 'N/A'
    }

def fetch_cfd_metal(ticker, sym_name, force_refresh=False):
    cache_key = f"CFD_{ticker}"
    now = time.time()
    if not force_refresh and cache_key in CACHE and (now - CACHE[cache_key]['time'] < CACHE_TTL):
        return CACHE[cache_key]['data']

    # 1. TradingView CFD
    url = 'https://scanner.tradingview.com/cfd/scan'
    payload = json.dumps({
        'symbols': {'tickers': [f"TVC:{ticker}"]},
        'columns': ['name', 'close', 'change', 'description']
    }).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=payload, headers=HTTP_HEADERS_TV)
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode('utf-8'))
            if d.get('data'):
                row = d['data'][0]['d']
                price = round(float(row[1]), 2) if row[1] is not None else 0
                if price > 0:
                    res = {
                        'symbol': ticker,
                        'usdPrice': price,
                        'changePct': round(float(row[2]), 2) if row[2] is not None else 0,
                        'name': row[3] or sym_name,
                        'source': 'TradingView CFD',
                        'success': True
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
    except Exception as e:
        logger.warning(f"TradingView CFD failed for {ticker}: {e}. Trying Yahoo Finance...")

    # 2. Yahoo Finance Fallback (GC=F for Gold, SI=F for Silver)
    yf_symbol = 'GC=F' if ticker == 'GOLD' else 'SI=F'
    try:
        yf_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}?interval=1d&range=1d"
        req = urllib.request.Request(yf_url, headers=HTTP_HEADERS_YAHOO)
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode('utf-8'))
            results = d.get('chart', {}).get('result', [])
            if results:
                meta = results[0].get('meta', {})
                price = meta.get('regularMarketPrice')
                prev = meta.get('chartPreviousClose') or meta.get('previousClose')
                if price and float(price) > 0:
                    price_val = round(float(price), 2)
                    chg_pct = round(((price_val - prev) / prev) * 100, 2) if (prev and prev > 0) else 0.0
                    res = {
                        'symbol': ticker,
                        'usdPrice': price_val,
                        'changePct': chg_pct,
                        'name': meta.get('shortName') or sym_name,
                        'source': 'Yahoo Finance Futures',
                        'success': True
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
    except Exception as e:
        logger.error(f"Yahoo Finance Futures failed for {ticker}: {e}")

    return {'symbol': ticker, 'usdPrice': 0, 'changePct': 0, 'success': False}

def fetch_crypto(std_sym, disp_name, force_refresh=False):
    cache_key = f"CRYPTO_{std_sym}"
    now = time.time()
    if not force_refresh and cache_key in CACHE and (now - CACHE[cache_key]['time'] < CACHE_TTL):
        return CACHE[cache_key]['data']

    # 1. TradingView Crypto Scan
    url = 'https://scanner.tradingview.com/crypto/scan'
    ticker = f"BINANCE:{std_sym}USDT"
    payload = json.dumps({
        'symbols': {'tickers': [ticker]},
        'columns': ['name', 'close', 'change', 'description']
    }).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=payload, headers=HTTP_HEADERS_TV)
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode('utf-8'))
            if d.get('data'):
                row = d['data'][0]['d']
                usd_val = float(row[1]) if row[1] is not None else 0
                if usd_val > 0:
                    usd_try = get_usd_try_rate()
                    try_val = round(usd_val * usd_try, 2)
                    res = {
                        'symbol': std_sym,
                        'name': disp_name,
                        'price': try_val,
                        'usdPrice': round(usd_val, 2),
                        'changePct': round(float(row[2]), 2) if row[2] is not None else 0,
                        'type': 'kripto',
                        'currency': 'TRY',
                        'source': 'TradingView (Binance)',
                        'updatedAt': int(time.time()),
                        'success': True
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
    except Exception as e:
        logger.warning(f"TradingView Crypto failed for {std_sym}: {e}. Trying Yahoo Finance...")

    # 2. Yahoo Finance Fallback
    try:
        yf_symbol = f"{std_sym}-USD"
        yf_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}?interval=1d&range=1d"
        req = urllib.request.Request(yf_url, headers=HTTP_HEADERS_YAHOO)
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode('utf-8'))
            results = d.get('chart', {}).get('result', [])
            if results:
                meta = results[0].get('meta', {})
                usd_val = meta.get('regularMarketPrice')
                prev = meta.get('chartPreviousClose') or meta.get('previousClose')
                if usd_val and float(usd_val) > 0:
                    usd_val = float(usd_val)
                    usd_try = get_usd_try_rate()
                    try_val = round(usd_val * usd_try, 2)
                    chg_pct = round(((usd_val - prev) / prev) * 100, 2) if (prev and prev > 0) else 0.0
                    res = {
                        'symbol': std_sym,
                        'name': meta.get('shortName') or disp_name,
                        'price': try_val,
                        'usdPrice': round(usd_val, 2),
                        'changePct': chg_pct,
                        'type': 'kripto',
                        'currency': 'TRY',
                        'source': 'Yahoo Finance (Crypto)',
                        'updatedAt': int(time.time()),
                        'success': True
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
    except Exception as e:
        logger.error(f"Yahoo Finance Crypto failed for {std_sym}: {e}")

    return {
        'symbol': std_sym,
        'name': disp_name,
        'price': 0,
        'error': f'Kripto verisi alınamadı ({std_sym})',
        'success': False,
        'source': 'N/A'
    }

def fetch_bist_quote(clean_sym, force_refresh=False):
    clean_sym = clean_bist_symbol(clean_sym)
    now = time.time()
    cache_key = f"BIST_{clean_sym}"
    if not force_refresh and cache_key in CACHE and (now - CACHE[cache_key]['time'] < CACHE_TTL):
        return CACHE[cache_key]['data']

    # 1. TradingView BIST Scanner
    url = 'https://scanner.tradingview.com/turkey/scan'
    payload = json.dumps({
        'symbols': {'tickers': [f"BIST:{clean_sym}"]},
        'columns': ['name', 'close', 'change', 'change_abs', 'description']
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers=HTTP_HEADERS_TV)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode('utf-8'))
            if d.get('data'):
                row = d['data'][0]['d']
                price = round(float(row[1]), 2) if row[1] is not None else 0
                if price > 0:
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
                        'updatedAt': int(time.time()),
                        'success': True
                    }
                    CACHE[cache_key] = {'data': res, 'time': now}
                    return res
    except Exception as e:
        logger.warning(f"TradingView BIST scan failed for {clean_sym}: {e}. Trying Yahoo Finance...")

    # 2. Yahoo Finance Fallback ({clean_sym}.IS)
    for endpoint in ['query1.finance.yahoo.com', 'query2.finance.yahoo.com']:
        try:
            yf_url = f"https://{endpoint}/v8/finance/chart/{clean_sym}.IS?interval=1d&range=1d"
            req = urllib.request.Request(yf_url, headers=HTTP_HEADERS_YAHOO)
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode('utf-8'))
                results = d.get('chart', {}).get('result', [])
                if results:
                    meta = results[0].get('meta', {})
                    price = meta.get('regularMarketPrice')
                    prev = meta.get('chartPreviousClose') or meta.get('previousClose')
                    if price and float(price) > 0:
                        price_val = round(float(price), 2)
                        chg_pct = round(((price_val - prev) / prev) * 100, 2) if (prev and prev > 0) else 0.0
                        chg_abs = round(price_val - prev, 2) if prev else 0.0
                        comp_name = meta.get('shortName') or meta.get('longName') or clean_sym
                        res = {
                            'symbol': clean_sym,
                            'name': comp_name,
                            'price': price_val,
                            'change': chg_abs,
                            'changePct': chg_pct,
                            'currency': 'TRY',
                            'type': 'hisse',
                            'source': 'Borsa Istanbul (Yahoo Finance)',
                            'updatedAt': int(time.time()),
                            'success': True
                        }
                        CACHE[cache_key] = {'data': res, 'time': now}
                        logger.info(f"Successfully retrieved live quote from Yahoo Finance for {clean_sym}: {price_val} TRY")
                        return res
        except Exception as e:
            logger.warning(f"Yahoo Finance endpoint {endpoint} failed for {clean_sym}: {e}")

    logger.error(f"[PORTFOLIO_API ERROR] All providers failed to fetch quote for BIST symbol: {clean_sym}")
    return {
        'symbol': clean_sym,
        'name': clean_sym,
        'price': 0,
        'error': f'Piyasa verisi alınamadı ({clean_sym}): Sağlayıcılar yanıt vermedi',
        'source': 'N/A',
        'success': False,
        'updatedAt': int(time.time())
    }

def fetch_market_data(raw_symbol, force_refresh=False):
    symbol = raw_symbol.upper().replace(' ', '_').strip()
    now = time.time()

    if not force_refresh and symbol in CACHE and (now - CACHE[symbol]['time'] < CACHE_TTL):
        return CACHE[symbol]['data']

    # Forex
    if symbol in ['USD', 'DOLAR', 'USD_TRY', 'USDTRY', 'USDTRY=X']:
        res = fetch_forex('USDTRY', force_refresh=force_refresh)
        res['symbol'] = 'USD'
        res['name'] = 'Amerikan Doları (USD)'
        return res

    if symbol in ['EUR', 'EURO', 'EUR_TRY', 'EURTRY', 'EURTRY=X']:
        res = fetch_forex('EURTRY', force_refresh=force_refresh)
        res['symbol'] = 'EUR'
        res['name'] = 'Euro (EUR)'
        return res

    if symbol in ['GBP', 'STERLIN', 'GBP_TRY', 'GBPTRY', 'GBPTRY=X']:
        res = fetch_forex('GBPTRY', force_refresh=force_refresh)
        res['symbol'] = 'GBP'
        res['name'] = 'İngiliz Sterlini (GBP)'
        return res

    # Crypto
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
        return fetch_crypto(std_sym, crypto_map[symbol], force_refresh=force_refresh)

    # Gold (Gram)
    if symbol in ['GRAM_ALTIN', 'ALTIN', 'GRAM', 'XAU_TRY']:
        gold_res = fetch_cfd_metal('GOLD', 'Gold Spot', force_refresh=force_refresh)
        ons_usd = gold_res.get('usdPrice', 0)
        usd_try = get_usd_try_rate(force_refresh=force_refresh)
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
                'source': f"{gold_res.get('source', 'TradingView')} (Calculated)",
                'updatedAt': int(time.time()),
                'success': True
            }
            CACHE[symbol] = {'data': res, 'time': now}
            return res
        return {
            'symbol': 'GRAM_ALTIN',
            'name': 'Gram Altın (24 Ayar)',
            'price': 0,
            'error': 'Altın ons/kur verisi alınamadı',
            'type': 'altin',
            'currency': 'TRY',
            'success': False
        }

    # Çeyrek Altın
    if symbol in ['CEYREK_ALTIN', 'CEYREK']:
        gram = fetch_market_data('GRAM_ALTIN', force_refresh=force_refresh)
        gram_price = gram.get('price', 0)
        if gram_price > 0:
            ceyrek_price = round(gram_price * 1.635 * 1.025, 2)
            res = {
                'symbol': 'CEYREK_ALTIN',
                'name': 'Çeyrek Altın (Darphane)',
                'price': ceyrek_price,
                'currency': 'TRY',
                'changePct': gram.get('changePct', 0),
                'type': 'altin',
                'source': 'Calculated',
                'updatedAt': int(time.time()),
                'success': True
            }
            CACHE[symbol] = {'data': res, 'time': now}
            return res
        return {
            'symbol': 'CEYREK_ALTIN',
            'name': 'Çeyrek Altın (Darphane)',
            'price': 0,
            'error': 'Çeyrek altın için gram fiyatı alınamadı',
            'type': 'altin',
            'currency': 'TRY',
            'success': False
        }

    # Gümüş (Gram)
    if symbol in ['GUMUS', 'GRAM_GUMUS', 'XAG_TRY']:
        silver_res = fetch_cfd_metal('SILVER', 'Silver Spot', force_refresh=force_refresh)
        ons_usd = silver_res.get('usdPrice', 0)
        usd_try = get_usd_try_rate(force_refresh=force_refresh)
        if ons_usd > 0 and usd_try > 0:
            gumus_tl = round((ons_usd / 31.1034768) * usd_try, 2)
            res = {
                'symbol': 'GUMUS',
                'name': 'Gram Gümüş (999 Ayar)',
                'price': gumus_tl,
                'currency': 'TRY',
                'changePct': silver_res.get('changePct', 0),
                'type': 'altin',
                'source': f"{silver_res.get('source', 'TradingView')} (Calculated)",
                'updatedAt': int(time.time()),
                'success': True
            }
            CACHE[symbol] = {'data': res, 'time': now}
            return res
        return {
            'symbol': 'GUMUS',
            'name': 'Gram Gümüş (999 Ayar)',
            'price': 0,
            'error': 'Gümüş ons/kur verisi alınamadı',
            'type': 'altin',
            'currency': 'TRY',
            'success': False
        }

    # Standart BIST hissesi
    res = fetch_bist_quote(symbol, force_refresh=force_refresh)
    if res.get('success'):
        CACHE[symbol] = {'data': res, 'time': now}
    elif admin_logger and not res.get('success'):
        admin_logger.log_critical("EXTERNAL_API_FAILURE", f"Hisse fiyatı çekilemedi ({symbol}): {res.get('error', 'Fiyat alınamadı')}")
    return res

def fetch_batch_quotes(symbols, force_refresh=False):
    results = {}
    bist_symbols = []

    for s in symbols:
        s_clean = s.strip().upper()
        if s_clean in ['USD', 'DOLAR', 'EUR', 'EURO', 'GBP', 'STERLIN', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'GRAM_ALTIN', 'ALTIN', 'CEYREK_ALTIN', 'GUMUS']:
            results[s_clean] = fetch_market_data(s_clean, force_refresh=force_refresh)
        else:
            bist_sym = clean_bist_symbol(s_clean)
            bist_symbols.append(bist_sym)

    if bist_symbols:
        tickers = [f"BIST:{sym}" for sym in bist_symbols]
        url = 'https://scanner.tradingview.com/turkey/scan'
        payload = json.dumps({
            'symbols': {'tickers': tickers},
            'columns': ['name', 'close', 'change', 'change_abs', 'description']
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers=HTTP_HEADERS_TV)
        try:
            with urllib.request.urlopen(req, timeout=6) as r:
                d = json.loads(r.read().decode('utf-8'))
                for row in d.get('data', []):
                    vals = row['d']
                    sym = vals[0]
                    price = round(float(vals[1]), 2) if vals[1] is not None else 0
                    if price > 0:
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
                            'updatedAt': int(time.time()),
                            'success': True
                        }
                        results[sym] = item_data
                        CACHE[sym] = {'data': item_data, 'time': time.time()}
                        CACHE[f"BIST_{sym}"] = {'data': item_data, 'time': time.time()}
        except Exception as e:
            logger.warning(f"Batch BIST scan from TradingView failed: {e}. Falling back to individual dual-provider fetch.")

    for s in symbols:
        s_clean = clean_bist_symbol(s)
        if s_clean not in results or results[s_clean].get('price', 0) <= 0:
            quote = fetch_market_data(s_clean, force_refresh=force_refresh)
            results[s_clean] = quote
            results[s] = quote

    return results
