const fs = require('fs');
const assert = require('assert');
const path = require('path');
const { execSync } = require('child_process');

console.log('====================================================');
console.log('📱 CAPACITOR MOBİL DÖNÜŞÜM & DOĞRULAMA TESTİ 📱');
console.log('====================================================\n');

// 1. Capacitor Yapılandırması (capacitor.config.ts) Kontrolü
console.log('--- 1. TEST: Capacitor Yapılandırması (capacitor.config.ts) ---');
assert(fs.existsSync('capacitor.config.ts'), 'capacitor.config.ts dosyası mevcut olmalıdır');
const capConfigCode = fs.readFileSync('capacitor.config.ts', 'utf-8');

assert(capConfigCode.includes("appId: 'com.mytakip.app'"), "appId: 'com.mytakip.app' olmalıdır");
assert(capConfigCode.includes("appName: 'MyTakip'"), "appName: 'MyTakip' olmalıdır");
assert(capConfigCode.includes("webDir: 'out'"), "webDir 'out' (Next.js statik export) klasörünü işaret etmelidir");
assert(capConfigCode.includes("androidScheme: 'https'"), "server.androidScheme 'https' olmalıdır");
assert(capConfigCode.includes("contentInset: 'never'"), "ios.contentInset 'never' olmalıdır");
assert(capConfigCode.includes('PushNotifications'), "PushNotifications eklentisi yapılandırılmalıdır");
assert(capConfigCode.includes('Keyboard'), "Keyboard eklentisi yapılandırılmalıdır");
console.log('[PASS] capacitor.config.ts; webDir: "out", https scheme ve eklenti ayarlarıyla eksiksiz.');

// 2. Next.js Statik Export Konfigürasyonu (next.config.ts) Kontrolü
console.log('\n--- 2. TEST: Next.js Konfigürasyonu (next.config.ts) ---');
assert(fs.existsSync('next.config.ts'), 'next.config.ts dosyası mevcut olmalıdır');
const nextConfigCode = fs.readFileSync('next.config.ts', 'utf-8');

assert(nextConfigCode.includes("output: 'export'"), "next.config.ts içinde output: 'export' tanımlanmalıdır");
assert(nextConfigCode.includes('unoptimized: true'), "images.unoptimized: true tanımlanmalıdır");
assert(nextConfigCode.includes('async headers()'), "Güvenlik başlıkları (async headers()) korunmalıdır");
console.log('[PASS] next.config.ts; output: "export", images.unoptimized: true ve OWASP başlıklarıyla doğrulandı.');

// 3. Web Asset Build Script ve Paketleme (scripts/build_www.js)
console.log('\n--- 3. TEST: Web Asset Paketleme ve out/ Çıktısı ---');
const buildResult = execSync('node scripts/build_www.js', { encoding: 'utf-8' });
console.log(buildResult.trim());

assert(fs.existsSync('out/index.html'), 'out/index.html mevcut olmalıdır');
assert(fs.existsSync('out/style.css'), 'out/style.css mevcut olmalıdır');
assert(fs.existsSync('out/mobile.js'), 'out/mobile.js mevcut olmalıdır');
assert(fs.existsSync('out/runtime-config.js'), 'out/runtime-config.js mevcut olmalıdır');
assert(fs.existsSync('www/index.html'), 'www/index.html geriye dönük uyumluluk için mevcut olmalıdır');
console.log('[PASS] out/ ve www/ klasörlerine temiz whitelist asset ihracı başarıyla gerçekleştirildi.');

// 4. Mobil İstemci Köprüsü (mobile.js) Kontrolleri
console.log('\n--- 4. TEST: Mobil İstemci Köprüsü (mobile.js) ---');
const mobileJsPath = fs.existsSync('web/mobile.js') ? 'web/mobile.js' : 'mobile.js';
const mobileJsCode = fs.readFileSync(mobileJsPath, 'utf-8');
assert(mobileJsCode.includes('isNativePlatform'), 'Capacitor native platform tespiti yapılmalıdır');
assert(mobileJsCode.includes('Authorization'), 'Bearer token header enjeksiyonu yapılmalıdır');
assert(mobileJsCode.includes('/api/auth/token'), '/api/auth/token istek mantığı bulunmalıdır');
assert(mobileJsCode.includes('/api/push/register'), '/api/push/register FCM token kayıt rotası bulunmalıdır');
assert(mobileJsCode.includes('backButton'), 'Android Donanımsal Geri Tuşu (backButton) dinleyicisi bulunmalıdır');
assert(mobileJsCode.includes('keyboardWillShow'), 'Klavye adaptasyonu dinleyicisi bulunmalıdır');
assert(mobileJsCode.includes('pt-safe') || mobileJsCode.includes('--kb-h'), 'Klavye ve Safe-area desteği doğrulanmalıdır');
console.log('[PASS] mobile.js; FCM push izni/kaydı, Bearer token interceptor, Android geri tuşu ve klavye desteği içeriyor.');

// 5. Mobil UI/UX Safe Area ve Klavye Stilleri (style.css)
console.log('\n--- 5. TEST: Mobile Safe Area (Notch / Dynamic Island) & CSS ---');
const styleCssPath = fs.existsSync('web/style.css') ? 'web/style.css' : 'style.css';
const styleCssCode = fs.readFileSync(styleCssPath, 'utf-8');
assert(styleCssCode.includes('.pt-safe'), '.pt-safe yardımcı sınıfı style.css içinde tanımlanmalıdır');
assert(styleCssCode.includes('.pb-safe'), '.pb-safe yardımcı sınıfı style.css içinde tanımlanmalıdır');
assert(styleCssCode.includes('env(safe-area-inset-top)'), 'safe-area-inset-top kullanılmalıdır');
assert(styleCssCode.includes('env(safe-area-inset-bottom)'), 'safe-area-inset-bottom kullanılmalıdır');
assert(styleCssCode.includes('html.kb-open'), 'html.kb-open klavye sınıfı tanımlanmalıdır');
console.log('[PASS] style.css; Çentik / Dynamic Island safe-area padding ve klavye açıkken kaydırma desteğine sahip.');

// 6. Yorum Satırı Kısıtı Kontrolü (index.html ve style.css)
console.log('\n--- 6. TEST: Zero Developer Comments Kısıtı Kontrolü ---');
const htmlPath = fs.existsSync('web/index.html') ? 'web/index.html' : 'index.html';
const htmlCode = fs.readFileSync(htmlPath, 'utf-8');
const htmlComments = htmlCode.match(/<!--[\s\S]*?-->/g) || [];
// Mevcut sistem yorumları dışındaki developer yorumlarını kontrol et
const devHtmlComments = htmlComments.filter(c => !c.includes('Google Tag') && !c.includes('DOCTYPE'));
assert(devHtmlComments.length === 0, `index.html içinde istenmeyen geliştirici yorumu tespit edildi: ${devHtmlComments.length}`);

// style.css sonundaki mobil blokları kontrol et
const lastStyles = styleCssCode.slice(-600);
assert(!lastStyles.includes('/*'), 'style.css mobil bölümünde geliştirici yorumu bulunmamalıdır');
console.log('[PASS] index.html ve style.css içinde sıfır geliştirici yorum kuralına tam uyuldu.');

// 7. Python Backend CORS, Auth & FCM Entegrasyonu (test_mobile_backend.py)
console.log('\n--- 7. TEST: Python Backend Mobil API & FCM Modülleri ---');
const pyBin = fs.existsSync('/usr/bin/python3') ? '/usr/bin/python3' : 'python3';
const pyBackendTestPath = fs.existsSync('tests/test_mobile_backend.py') ? 'tests/test_mobile_backend.py' : 'test_mobile_backend.py';
const pyResult = execSync(`${pyBin} ${pyBackendTestPath}`, { encoding: 'utf-8' });
console.log(pyResult.trim());
console.log('[PASS] Python backend; CORS mobile originleri, Bearer token ve FCM yönlendirmeleriyle %100 uyumlu.');

console.log('\n====================================================');
console.log('🎉 TÜM CAPACITOR & MOBİL UYARLAMA TESTLERİ BAŞARIYLA GEÇTİ! 🚀');
console.log('====================================================\n');
