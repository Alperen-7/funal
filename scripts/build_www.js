#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TARGET_DIRS = [path.join(ROOT, 'out'), path.join(ROOT, 'www')];
const OUT_DIR = TARGET_DIRS[0];

// Yalnizca uygulamanin calismasi icin gereken dosyalar. Whitelist kullaniyoruz ki
// .env, secrets/, *.py, *.sql, test dosyalari gibi seyler asla mobil pakete girmesin.
const WEB_FILES = [
  'index.html',
  'style.css',
  'config.js',
  'bist_stocks.js',
  'mobile.js',
];

function resolveApiBaseUrl() {
  const raw = (process.env.API_BASE_URL || '').trim().replace(/\/+$/, '');
  if (!raw) return '';
  let parsed;
  try {
    parsed = new URL(raw);
  } catch (e) {
    throw new Error('API_BASE_URL gecerli bir URL degil: ' + raw);
  }
  if (parsed.protocol !== 'https:' && parsed.hostname !== 'localhost' && parsed.hostname !== '127.0.0.1') {
    throw new Error('API_BASE_URL https olmali (magaza kurallari ve ATS/cleartext kisitlari): ' + raw);
  }
  return parsed.origin + parsed.pathname.replace(/\/+$/, '');
}

function build() {
  const apiBase = resolveApiBaseUrl();
  const runtime = 'window.MYTAKIP_RUNTIME = ' + JSON.stringify({ API_BASE_URL: apiBase }) + ';\n';

  for (const dir of TARGET_DIRS) {
    fs.rmSync(dir, { recursive: true, force: true });
    fs.mkdirSync(dir, { recursive: true });

    for (const file of WEB_FILES) {
      const src = path.join(ROOT, file);
      if (!fs.existsSync(src)) {
        throw new Error('Eksik web dosyasi: ' + file);
      }
      fs.copyFileSync(src, path.join(dir, file));
    }

    fs.writeFileSync(path.join(dir, 'runtime-config.js'), runtime, 'utf8');
  }

  console.log('out/ ve www/ hazir: ' + WEB_FILES.length + ' dosya + runtime-config.js');
  if (!apiBase) {
    console.warn('UYARI: API_BASE_URL tanimli degil. Mobil uygulama push kaydi ve /api cagrilarini yapamaz.');
    console.warn('       Ornek: API_BASE_URL=https://api.ornek.com npm run build:web');
  }
}

if (require.main === module) {
  build();
}

module.exports = { build, resolveApiBaseUrl, WEB_FILES, OUT_DIR };
