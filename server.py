#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import http.server
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import urllib.request
import urllib.parse
import time
import os
import re
import portfolio_engine

PORT = int(os.environ.get('PORT', 8765))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

CACHE = portfolio_engine.CACHE
CACHE_TTL = portfolio_engine.CACHE_TTL

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
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Pragma, Cache-Control')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Vary', 'Origin')
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
