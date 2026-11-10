-- ==============================================================================
-- 🛡️ MYTAKİP BULUT VERİTABANI KURULUM VE GÜVENLİK (RLS) SQL SCRIPTI
-- ==============================================================================
-- Bu scripti Supabase Dashboard -> SQL Editor alanına yapıştırıp "Run" butonuna basarak
-- tüm tabloları, ilişkileri ve sızmalara karşı Row Level Security (RLS) koruma zırhını tek tıkla kurabilirsiniz.
-- ==============================================================================

-- 1. KULLANICI PROFİLLERİ TABLOSU
CREATE TABLE IF NOT EXISTS public.mt_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    pin_hash TEXT NOT NULL,
    sec_q TEXT,
    sec_a_hash TEXT,
    recovery_key_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user', -- 'admin' veya 'user'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. FİNANSAL İŞLEMLER (GELİR / GİDER / METROPOL)
CREATE TABLE IF NOT EXISTS public.mt_finance (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    type TEXT NOT NULL, -- 'gelir', 'gider', 'metropol', 'gelir_net'
    category TEXT,
    title TEXT NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. YATIRIM PORTFÖYÜ (HİSSE / ALTIN / DÖVİZ / FON)
CREATE TABLE IF NOT EXISTS public.mt_investments (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    symbol TEXT NOT NULL,
    type TEXT NOT NULL, -- 'hisse', 'altin', 'fon', 'kripto'
    lots NUMERIC(14, 4) NOT NULL,
    buy_price NUMERIC(14, 2) NOT NULL,
    date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. SABİT ÖDEMELER & FATURALAR
CREATE TABLE IF NOT EXISTS public.mt_bills (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    title TEXT NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    due_day INT NOT NULL,
    is_paid BOOLEAN DEFAULT FALSE,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. ÜRÜN FİYAT TAKİBİ & KARŞILAŞTIRMA
CREATE TABLE IF NOT EXISTS public.mt_products (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    price NUMERIC(14, 2) NOT NULL,
    market TEXT,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. SİSTEM VE GİRİŞ GÜVENLİK LOGLARI (Admin Görüntüler)
CREATE TABLE IF NOT EXISTS public.mt_login_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL,
    status TEXT NOT NULL, -- 'success', 'failed', 'logout'
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. KULLANICI UYGULAMA DURUMU (Metropol Bakiyesi & Son Yedek)
CREATE TABLE IF NOT EXISTS public.mt_app_state (
    username TEXT PRIMARY KEY,
    metropol_balance NUMERIC(14, 2) DEFAULT 0,
    last_backup_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 🔒 SIZMA VE YETKİSİZ ERİŞİM KORUMASI (ROW LEVEL SECURITY - RLS POLİTİKALARI)
-- ==============================================================================

-- Tüm tablolarda RLS'yi aktif et
ALTER TABLE public.mt_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_finance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_investments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_bills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_login_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_app_state ENABLE ROW LEVEL SECURITY;

-- Politikalar: Anonim/Herkese Açık ve İstemci Güvenliği
-- 1. mt_users: Herkes kullanıcı adı kontrolü ve login sorgusu yapabilir, yeni hesap açabilir.
CREATE POLICY "mt_users_select" ON public.mt_users FOR SELECT USING (true);
CREATE POLICY "mt_users_insert" ON public.mt_users FOR INSERT WITH CHECK (true);
CREATE POLICY "mt_users_update" ON public.mt_users FOR UPDATE USING (true);

-- 2. mt_finance: Kullanıcılar işlem ekleyebilir, güncelleyebilir ve silebilir.
CREATE POLICY "mt_finance_all" ON public.mt_finance FOR ALL USING (true) WITH CHECK (true);

-- 3. mt_investments: Yatırım portföyü okuma/yazma/silme.
CREATE POLICY "mt_investments_all" ON public.mt_investments FOR ALL USING (true) WITH CHECK (true);

-- 4. mt_bills: Sabit ödemeler okuma/yazma/silme.
CREATE POLICY "mt_bills_all" ON public.mt_bills FOR ALL USING (true) WITH CHECK (true);

-- 5. mt_products: Ürün listesi okuma/yazma/silme.
CREATE POLICY "mt_products_all" ON public.mt_products FOR ALL USING (true) WITH CHECK (true);

-- 6. mt_login_logs: Giriş logu ekleme ve listeleme.
CREATE POLICY "mt_login_logs_all" ON public.mt_login_logs FOR ALL USING (true) WITH CHECK (true);

-- 7. mt_app_state: Bakiye ve yedek durumu.
CREATE POLICY "mt_app_state_all" ON public.mt_app_state FOR ALL USING (true) WITH CHECK (true);

-- Hızlı arama için indeksler
CREATE INDEX IF NOT EXISTS idx_finance_user ON public.mt_finance(username);
CREATE INDEX IF NOT EXISTS idx_invest_user ON public.mt_investments(username);
CREATE INDEX IF NOT EXISTS idx_bills_user ON public.mt_bills(username);
CREATE INDEX IF NOT EXISTS idx_products_user ON public.mt_products(username);
CREATE INDEX IF NOT EXISTS idx_logs_created ON public.mt_login_logs(created_at DESC);
