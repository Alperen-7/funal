CREATE TABLE IF NOT EXISTS public.mt_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    pin_hash TEXT NOT NULL,
    sec_q TEXT,
    sec_a_hash TEXT,
    recovery_key_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.mt_finance (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    type TEXT NOT NULL,
    category TEXT,
    title TEXT NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.mt_investments (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    symbol TEXT NOT NULL,
    type TEXT NOT NULL,
    lots NUMERIC(14, 4) NOT NULL,
    buy_price NUMERIC(14, 2) NOT NULL,
    date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS public.mt_login_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.mt_app_state (
    username TEXT PRIMARY KEY,
    metropol_balance NUMERIC(14, 2) DEFAULT 0,
    last_backup_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.mt_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_finance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_investments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_bills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_login_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt_app_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY "mt_users_select" ON public.mt_users FOR SELECT USING (true);
CREATE POLICY "mt_users_insert" ON public.mt_users FOR INSERT WITH CHECK (true);
CREATE POLICY "mt_users_update" ON public.mt_users FOR UPDATE USING (true);

CREATE POLICY "mt_finance_all" ON public.mt_finance FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "mt_investments_all" ON public.mt_investments FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "mt_bills_all" ON public.mt_bills FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "mt_products_all" ON public.mt_products FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "mt_login_logs_all" ON public.mt_login_logs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "mt_app_state_all" ON public.mt_app_state FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_finance_user ON public.mt_finance(username);
CREATE INDEX IF NOT EXISTS idx_invest_user ON public.mt_investments(username);
CREATE INDEX IF NOT EXISTS idx_bills_user ON public.mt_bills(username);
CREATE INDEX IF NOT EXISTS idx_products_user ON public.mt_products(username);
CREATE INDEX IF NOT EXISTS idx_logs_created ON public.mt_login_logs(created_at DESC);
