

const APP_CONFIG = {
  
  STORAGE_MARKET:   'mt_v3',
  STORAGE_FINANCE:  'gg_v1',
  STORAGE_METROPOL: 'mt_metropol_v1',
  STORAGE_INVEST:   'mt_invest_v1',
  STORAGE_BILLS:    'mt_bills_v1',       
  STORAGE_USERS:    'mt_users_v2',       
  STORAGE_AUTH:     'mytakip_auth_v2',   
  STORAGE_OCR_KEY:  'ocrspace_key',

  AUTH: {
    DEFAULT_USER: 'admin',
    PIN_LENGTH:   6,
    SESSION_EXPIRE_HOURS: 24,
  },

  MARKET_DATA: {
    LOCAL_ENDPOINT: '/api/quote',        
    IS_FREE: true,                       
  },

  OCR_SPACE_ENDPOINT: 'https://api.ocr.space/parse/image',

  OCR_RATE_LIMIT: {
    MIN_INTERVAL_MS:  12_000,
    MAX_PER_HOUR:     10,
    STORAGE_KEY:      'ocr_rl',
  },

  TESSERACT_LANGS: 'tur+eng',
  TESSERACT_OEM:   1,

  SUPABASE: {
    ENABLED: true,
    URL: 'https://huwfyjwutmpsgkoqkvcx.supabase.co',
    ANON_KEY: 'sb_publishable_yXR8MSqvTCbBnh4VG2sNWg_SfW3dzj1',
  },

  APP_NAME:    'MyTakip',
  APP_VERSION: '2.3.0',
};

if (typeof window !== 'undefined') {
  if (typeof document !== 'undefined') {
    try {
      const s2 = document.createElement('script');
      s2.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2';
      document.head.appendChild(s2);
    } catch(e) {}
  }
  window.APP_CONFIG = APP_CONFIG;
}
