#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import http.server
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import urllib.request
import urllib.parse
import time
import sys
import os
import re
import portfolio_engine
import mobile_api

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR) if os.path.basename(BACKEND_DIR) == 'backend' else BACKEND_DIR
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    import scripts.admin_logger as admin_logger
except ImportError:
    try:
        import admin_logger
    except ImportError:
        admin_logger = None

PORT = int(os.environ.get('PORT', 8765))
WEB_DIR = os.path.join(PROJECT_ROOT, 'web')
DIRECTORY = WEB_DIR if os.path.isdir(WEB_DIR) else PROJECT_ROOT

CACHE = portfolio_engine.CACHE
CACHE_TTL = portfolio_engine.CACHE_TTL

SYMBOL_REGEX = re.compile(r'^[A-Z0-9_\.]{1,16}$')

class MyTakipHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def get_cors_origin(self):
        return mobile_api.resolve_cors_origin(self.headers.get('Origin', ''))

    def send_cors_headers(self):
        for name, value in mobile_api.cors_headers(self.headers.get('Origin', '')):
            self.send_header(name, value)

    def read_request_body(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return b''
        return self.rfile.read(min(length, mobile_api.MAX_BODY_BYTES + 1))

    def handle_mobile_api(self):
        clean_path = urllib.parse.urlparse(self.path).path
        if not mobile_api.is_mobile_path(clean_path):
            self.send_json({'error': 'Not Found'}, status=404)
            return
        try:
            body = self.read_request_body()
            result = mobile_api.dispatch(self.command, clean_path, self.headers, body)
            status, payload = result if result is not None else (404, {'error': 'Not Found'})
            self.send_json(payload, status=status)
        except Exception as e:
            if admin_logger:
                admin_logger.log_critical("INTERNAL_SERVER_ERROR_500", f"Mobil API 500 hatası: {e}", exc=e)
            self.send_json({'error': 'Internal Server Error'}, status=500)

    def do_POST(self):
        clean_path = urllib.parse.urlparse(self.path).path
        if clean_path == '/api/portfolio/pnl':
            try:
                body = self.read_request_body()
                payload = json.loads(body.decode('utf-8')) if body else {}
                trades = payload.get('trades', payload.get('transactions', []))
                quotes = payload.get('quotes', {})
                usd_rate = payload.get('usd_try_rate')
                if not quotes and payload.get('fetch_live', True):
                    syms = list(set(portfolio_engine.clean_bist_symbol(t.get('symbol')) for t in trades if t.get('symbol')))
                    if syms:
                        quotes = self.fetch_batch_quotes(syms)
                result = portfolio_engine.calculate_portfolio_pnl(trades, quotes, usd_rate)
                self.send_json(result)
                return
            except Exception as e:
                self.send_json({'error': str(e)}, status=400)
                return
        self.handle_mobile_api()

    def do_DELETE(self):
        self.handle_mobile_api()

    def do_GET(self):
        try:
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
                force_refresh = bool(params.get('_t'))
                data = self.fetch_batch_quotes(symbols, force_refresh=force_refresh)
                self.send_json(data)
                return

            if clean_path == '/api/quote':
                params = urllib.parse.parse_qs(parsed.query)
                symbol = params.get('symbol', [''])[0].strip().upper()

                if not symbol or not SYMBOL_REGEX.match(symbol):
                    self.send_json({'error': 'Geçersiz veya eksik sembol parametresi. Yalnızca standart borsa sembolleri kabul edilir.'}, status=400)
                    return

                force_refresh = bool(params.get('_t'))
                data = self.fetch_market_data(symbol, force_refresh=force_refresh)
                self.send_json(data)
                return

            if clean_path == '/api/portfolio/pnl':
                params = urllib.parse.parse_qs(parsed.query)
                trades_json = params.get('trades', [''])[0]
                trades = json.loads(trades_json) if trades_json else []
                symbols = list(set(portfolio_engine.clean_bist_symbol(t.get('symbol')) for t in trades if t.get('symbol')))
                quotes = self.fetch_batch_quotes(symbols) if symbols else {}
                data = portfolio_engine.calculate_portfolio_pnl(trades, quotes)
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
        except Exception as e:
            if admin_logger:
                admin_logger.log_critical("INTERNAL_SERVER_ERROR_500", f"İşlenemeyen 500 sunucu hatası: {e}", exc=e)
            self.send_json({'error': 'Internal Server Error', 'detail': str(e)}, status=500)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_cors_headers()
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def get_usd_try_rate(self, force_refresh=False):
        return portfolio_engine.get_usd_try_rate(force_refresh=force_refresh)

    def fetch_forex(self, pair, force_refresh=False):
        return portfolio_engine.fetch_forex(pair, force_refresh=force_refresh)

    def fetch_cfd_metal(self, ticker, sym_name, force_refresh=False):
        return portfolio_engine.fetch_cfd_metal(ticker, sym_name, force_refresh=force_refresh)

    def fetch_crypto(self, std_sym, disp_name, force_refresh=False):
        return portfolio_engine.fetch_crypto(std_sym, disp_name, force_refresh=force_refresh)

    def fetch_market_data(self, raw_symbol, force_refresh=False):
        return portfolio_engine.fetch_market_data(raw_symbol, force_refresh=force_refresh)

    def fetch_batch_quotes(self, symbols, force_refresh=False):
        return portfolio_engine.fetch_batch_quotes(symbols, force_refresh=force_refresh)

def wsgi_app(environ, start_response):
    path = environ.get('PATH_INFO', '/')
    if not path or path == '/':
        path = '/index.html'

    clean_path = path.split('?')[0]

    method = environ.get('REQUEST_METHOD', 'GET').upper()
    origin = environ.get('HTTP_ORIGIN', '')

    if method == 'OPTIONS' and clean_path.startswith('/api/'):
        start_response('204 No Content', mobile_api.cors_headers(origin) + [('Content-Length', '0')])
        return [b'']

    if mobile_api.is_mobile_path(clean_path):
        try:
            length = int(environ.get('CONTENT_LENGTH') or 0)
        except ValueError:
            length = 0
        raw_body = environ['wsgi.input'].read(min(length, mobile_api.MAX_BODY_BYTES + 1)) if length > 0 else b''
        status, payload = mobile_api.dispatch(
            method, clean_path, {'Authorization': environ.get('HTTP_AUTHORIZATION')}, raw_body
        )
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        try:
            phrase = http.HTTPStatus(status).phrase
        except ValueError:
            phrase = 'Unknown'
        start_response('%d %s' % (status, phrase), [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Cache-Control', 'no-store'),
            ('Content-Length', str(len(body))),
        ] + mobile_api.cors_headers(origin))
        return [body]

    if clean_path == '/api/quotes':
        qs = environ.get('QUERY_STRING', '')
        params = urllib.parse.parse_qs(qs)
        symbols_str = params.get('symbols', [''])[0].strip().upper()
        raw_symbols = [s.strip() for s in symbols_str.split(',') if s.strip()]
        symbols = [s for s in raw_symbols if SYMBOL_REGEX.match(s)]
        force_refresh = bool(params.get('_t'))
        inst = MyTakipHandler.__new__(MyTakipHandler)
        data = inst.fetch_batch_quotes(symbols, force_refresh=force_refresh) if symbols else {}
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        start_response('200 OK', [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Access-Control-Allow-Origin', '*'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
            ('Expires', '0')
        ])
        return [body]

    if clean_path == '/api/quote':
        qs = environ.get('QUERY_STRING', '')
        params = urllib.parse.parse_qs(qs)
        symbol = params.get('symbol', [''])[0].strip().upper()
        force_refresh = bool(params.get('_t'))
        inst = MyTakipHandler.__new__(MyTakipHandler)
        data = inst.fetch_market_data(symbol, force_refresh=force_refresh) if (symbol and SYMBOL_REGEX.match(symbol)) else {'error': 'Geçersiz sembol'}
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        start_response('200 OK', [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Access-Control-Allow-Origin', '*'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
            ('Expires', '0')
        ])
        return [body]

    if clean_path == '/api/portfolio/pnl':
        try:
            length = int(environ.get('CONTENT_LENGTH') or 0)
        except ValueError:
            length = 0
        raw_body = environ['wsgi.input'].read(length) if length > 0 else b''
        payload = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        trades = payload.get('trades', payload.get('transactions', []))
        quotes = payload.get('quotes', {})
        usd_rate = payload.get('usd_try_rate')
        if not quotes and payload.get('fetch_live', True):
            syms = list(set(portfolio_engine.clean_bist_symbol(t.get('symbol')) for t in trades if t.get('symbol')))
            if syms:
                inst = MyTakipHandler.__new__(MyTakipHandler)
                quotes = inst.fetch_batch_quotes(syms)
        result = portfolio_engine.calculate_portfolio_pnl(trades, quotes, usd_rate)
        body = json.dumps(result, ensure_ascii=False).encode('utf-8')
        start_response('200 OK', [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Access-Control-Allow-Origin', '*'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
            ('Expires', '0'),
            ('Content-Length', str(len(body)))
        ])
        return [body]

    rel_path = clean_path.lstrip('/')
    file_path = os.path.join(DIRECTORY, rel_path)
    if os.path.abspath(file_path).startswith(DIRECTORY) and os.path.isfile(file_path):
        mime_types = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon'
        }
        ext = os.path.splitext(file_path)[1].lower()
        content_type = mime_types.get(ext, 'application/octet-stream')
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            start_response('200 OK', [
                ('Content-Type', content_type),
                ('Access-Control-Allow-Origin', '*')
            ])
            return [content]
        except Exception:
            pass

    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return [b'Not Found']

app = wsgi_app
application = wsgi_app
handler = wsgi_app

if __name__ == '__main__':
    with ThreadingHTTPServer(('', PORT), MyTakipHandler) as httpd:
        print(f"MyTakip Threaded Server & BIST (All 650+ Stocks)/Forex/Crypto API running at http://localhost:{PORT}")
        httpd.serve_forever()
