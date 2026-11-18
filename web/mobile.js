(function (global) {
  'use strict';

  var doc = global.document;
  var cap = global.Capacitor;
  var runtime = global.MYTAKIP_RUNTIME || {};
  var API_BASE = String(runtime.API_BASE_URL || '').replace(/\/+$/, '');
  var isNative = !!(cap && typeof cap.isNativePlatform === 'function' && cap.isNativePlatform());
  var platform = isNative && typeof cap.getPlatform === 'function' ? cap.getPlatform() : 'web';

  var TOKEN_KEY = 'mt_api_token_v1';
  var FCM_TOKEN_KEY = 'mt_fcm_token_v1';
  var PROTECTED_PREFIXES = ['/api/push/'];
  var REGISTRATION_TIMEOUT_MS = 15000;
  var EXIT_CONFIRM_WINDOW_MS = 2000;

  var nativeFetch = typeof global.fetch === 'function' ? global.fetch.bind(global) : null;
  var pluginCache = {};
  var pushState = { listening: false, waiter: null, credentials: null };
  var lastBackAt = 0;

  function noop() {}

  function getPlugin(name) {
    if (!isNative) return null;
    if (!pluginCache[name]) pluginCache[name] = cap.registerPlugin(name);
    return pluginCache[name];
  }

  function storageGet(key) {
    try { return global.localStorage.getItem(key); } catch (e) { return null; }
  }

  function storageSet(key, value) {
    try { global.localStorage.setItem(key, value); } catch (e) {}
  }

  function storageRemove(key) {
    try { global.localStorage.removeItem(key); } catch (e) {}
  }

  function isProtectedPath(path) {
    for (var i = 0; i < PROTECTED_PREFIXES.length; i++) {
      if (path.indexOf(PROTECTED_PREFIXES[i]) === 0) return true;
    }
    return false;
  }

  function readCachedToken() {
    var raw = storageGet(TOKEN_KEY);
    if (!raw) return null;
    try {
      var obj = JSON.parse(raw);
      if (!obj || !obj.token || !obj.exp) return null;
      if (obj.exp * 1000 < Date.now() + 60000) return null;
      return obj.token;
    } catch (e) {
      return null;
    }
  }

  function clearApiToken() {
    storageRemove(TOKEN_KEY);
  }

  function installFetchInterceptor() {
    if (!nativeFetch || global.__mytakipFetchPatched) return;
    global.__mytakipFetchPatched = true;
    global.fetch = function (input, init) {
      if (typeof input !== 'string' || input.indexOf('/api/') !== 0) {
        return nativeFetch(input, init);
      }
      var path = input.split('?')[0];
      var opts = Object.assign({}, init || {});
      opts.credentials = 'omit';
      if (isProtectedPath(path)) {
        var headers = new Headers(opts.headers || {});
        var token = readCachedToken();
        if (token) headers.set('Authorization', 'Bearer ' + token);
        opts.headers = headers;
      }
      return nativeFetch(API_BASE ? API_BASE + input : input, opts);
    };
  }

  async function requestApiToken(credentials) {
    if (!API_BASE) throw new Error('API_BASE_URL tanımlı değil.');
    if (!credentials || !credentials.username || !credentials.pinHash) {
      throw new Error('Oturum bilgisi eksik.');
    }
    var res = await nativeFetch(API_BASE + '/api/auth/token', {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: credentials.username, pin_hash: credentials.pinHash })
    });
    if (!res.ok) throw new Error('Sunucu kimlik doğrulaması başarısız (' + res.status + ').');
    var data = await res.json();
    if (!data || !data.token) throw new Error('Sunucudan geçersiz token yanıtı.');
    storageSet(TOKEN_KEY, JSON.stringify({
      token: data.token,
      exp: Math.floor(Date.now() / 1000) + Number(data.expires_in || 3600)
    }));
    return data.token;
  }

  async function ensureApiToken(credentials) {
    return readCachedToken() || requestApiToken(credentials);
  }

  async function authorizedRequest(path, method, body, credentials) {
    await ensureApiToken(credentials);
    var send = function () {
      return global.fetch(path, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
    };
    var res = await send();
    if (res.status === 401) {
      clearApiToken();
      await ensureApiToken(credentials);
      res = await send();
    }
    return res;
  }

  async function sendTokenToBackend(fcmToken, credentials) {
    var res = await authorizedRequest('/api/push/register', 'POST', {
      fcm_token: fcmToken,
      platform: platform
    }, credentials);
    if (!res.ok) throw new Error('Push kaydı sunucuya iletilemedi (' + res.status + ').');
    storageSet(FCM_TOKEN_KEY, fcmToken);
  }

  function handleNotificationTap(event) {
    var data = (event && event.notification && event.notification.data) || {};
    if (data.screen === 'bills' && typeof global.goApp === 'function') {
      global.goApp('finance');
      if (typeof global.switchFinTab === 'function') global.switchFinTab('bills');
    }
  }

  async function ensurePushListeners(PN) {
    if (pushState.listening) return;
    pushState.listening = true;
    await PN.addListener('registration', function (t) {
      var token = t && t.value;
      if (!token) return;
      if (pushState.waiter) {
        pushState.waiter.resolve(token);
      } else if (pushState.credentials) {
        sendTokenToBackend(token, pushState.credentials).catch(noop);
      }
    });
    await PN.addListener('registrationError', function (e) {
      if (pushState.waiter) {
        pushState.waiter.reject(new Error((e && e.error) || 'Push kaydı başarısız.'));
      }
    });
    await PN.addListener('pushNotificationReceived', function (n) {
      if (typeof global.toast === 'function' && n) {
        global.toast((n.title ? n.title + ': ' : '') + (n.body || ''), 'info');
      }
    });
    await PN.addListener('pushNotificationActionPerformed', handleNotificationTap);
  }

  function waitForRegistration(PN) {
    return new Promise(function (resolve, reject) {
      var timer = setTimeout(function () {
        pushState.waiter = null;
        reject(new Error('Push kaydı zaman aşımına uğradı.'));
      }, REGISTRATION_TIMEOUT_MS);
      pushState.waiter = {
        resolve: function (v) { clearTimeout(timer); pushState.waiter = null; resolve(v); },
        reject: function (e) { clearTimeout(timer); pushState.waiter = null; reject(e); }
      };
      PN.register().catch(function (e) {
        if (pushState.waiter) pushState.waiter.reject(e);
      });
    });
  }

  async function registerPush(credentials) {
    if (!isNative) {
      return { ok: false, reason: 'not-native', message: 'Native push yalnızca mobil uygulamada kullanılabilir.' };
    }
    if (!API_BASE) {
      return { ok: false, reason: 'no-api', message: 'Sunucu adresi (API_BASE_URL) yapılandırılmamış.' };
    }
    try {
      var PN = getPlugin('PushNotifications');
      var perm = await PN.checkPermissions();
      if (perm.receive === 'prompt' || perm.receive === 'prompt-with-rationale') {
        perm = await PN.requestPermissions();
      }
      if (perm.receive !== 'granted') {
        return { ok: false, reason: 'denied', message: 'Bildirim izni verilmedi. Cihaz ayarlarından izin verebilirsiniz.' };
      }
      pushState.credentials = credentials;
      await ensurePushListeners(PN);
      var token = await waitForRegistration(PN);
      await sendTokenToBackend(token, credentials);
      return { ok: true };
    } catch (e) {
      return { ok: false, reason: 'error', message: (e && e.message) || 'Push kaydı başarısız.' };
    }
  }

  async function unregisterPush(credentials) {
    if (!isNative) return { ok: false, reason: 'not-native' };
    pushState.credentials = null;
    var token = storageGet(FCM_TOKEN_KEY);
    var backendOk = true;
    if (token && API_BASE) {
      try {
        var res = await authorizedRequest('/api/push/register', 'DELETE', { fcm_token: token }, credentials);
        backendOk = res.ok;
      } catch (e) {
        backendOk = false;
      }
    }
    try {
      await getPlugin('PushNotifications').unregister();
    } catch (e) {}
    storageRemove(FCM_TOKEN_KEY);
    return { ok: backendOk };
  }

  function closeTopOverlay() {
    var open = doc.querySelectorAll('.ov.open');
    if (!open.length) return false;
    var ov = open[open.length - 1];
    var match = (ov.getAttribute('onclick') || '').match(/ovClick\(event,\s*'[^']+',\s*([A-Za-z_$][\w$]*)\s*\)/);
    var closer = match ? global[match[1]] : null;
    if (typeof closer === 'function') {
      closer();
    } else {
      ov.classList.remove('open');
    }
    return true;
  }

  function authScreenVisible() {
    var auth = doc.getElementById('authScreen');
    return !!auth && !auth.classList.contains('hidden');
  }

  function handleAuthBack() {
    if (!authScreenVisible()) return false;
    var login = doc.getElementById('authViewLogin');
    if (login && !login.classList.contains('active') && typeof global.showAuthView === 'function') {
      global.showAuthView('login');
      return true;
    }
    return false;
  }

  function handleAppBack() {
    if (authScreenVisible()) return false;
    if (typeof currentApp !== 'undefined' && currentApp !== 'home' && currentApp !== 'admin' && typeof global.goHome === 'function') {
      global.goHome();
      return true;
    }
    return false;
  }

  function exitOrWarn(AppPlugin) {
    var now = Date.now();
    if (now - lastBackAt < EXIT_CONFIRM_WINDOW_MS) {
      AppPlugin.exitApp();
      return;
    }
    lastBackAt = now;
    if (typeof global.toast === 'function') global.toast('Çıkmak için tekrar geri tuşuna basın', 'info');
  }

  function handleBackButton(AppPlugin) {
    if (closeTopOverlay()) return;
    if (handleAuthBack()) return;
    if (handleAppBack()) return;
    exitOrWarn(AppPlugin);
  }

  function setupBackButton() {
    var AppPlugin = getPlugin('App');
    AppPlugin.addListener('backButton', function () { handleBackButton(AppPlugin); });
  }

  function scrollActiveIntoView() {
    setTimeout(function () {
      var el = doc.activeElement;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    }, 60);
  }

  function setupKeyboard() {
    var KB = getPlugin('Keyboard');
    var root = doc.documentElement;
    KB.addListener('keyboardWillShow', function (info) {
      root.classList.add('kb-open');
      root.style.setProperty('--kb-h', ((info && info.keyboardHeight) || 0) + 'px');
      scrollActiveIntoView();
    });
    KB.addListener('keyboardDidShow', scrollActiveIntoView);
    KB.addListener('keyboardWillHide', function () {
      root.classList.remove('kb-open');
      root.style.removeProperty('--kb-h');
    });
  }

  function init() {
    installFetchInterceptor();
    if (!isNative) return;
    doc.documentElement.classList.add('is-native', 'platform-' + platform);
    if (!API_BASE && global.console) {
      global.console.warn('MyTakip: API_BASE_URL tanımlı değil; /api çağrıları ve push kaydı çalışmaz.');
    }
    setupBackButton();
    setupKeyboard();
  }

  init();

  global.MyTakipMobile = {
    isNative: isNative,
    platform: platform,
    apiBaseUrl: API_BASE,
    registerPush: registerPush,
    unregisterPush: unregisterPush,
    clearApiToken: clearApiToken,
    ensureApiToken: ensureApiToken,
    handleBackButton: handleBackButton
  };
})(typeof window !== 'undefined' ? window : globalThis);
