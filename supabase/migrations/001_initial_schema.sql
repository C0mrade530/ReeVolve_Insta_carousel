-- =============================================
-- RealPost Pro — Initial Database Schema
-- Supabase (PostgreSQL) with RLS
-- Safe to re-run (IF NOT EXISTS everywhere)
-- =============================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================
-- 1. PROFILES (extends Supabase Auth users)
-- =============================================
-- Если таблица profiles уже есть — добавляем недостающие колонки
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'profiles') THEN
        CREATE TABLE public.profiles (
            id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'manager' CHECK (role IN ('admin', 'manager')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    ELSE
        -- Добавляем колонки если их нет
        BEGIN ALTER TABLE public.profiles ADD COLUMN role TEXT NOT NULL DEFAULT 'manager'; EXCEPTION WHEN duplicate_column THEN NULL; END;
        BEGIN ALTER TABLE public.profiles ADD COLUMN name TEXT NOT NULL DEFAULT ''; EXCEPTION WHEN duplicate_column THEN NULL; END;
        BEGIN ALTER TABLE public.profiles ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(); EXCEPTION WHEN duplicate_column THEN NULL; END;
    END IF;
END $$;

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Policies (drop if exist to avoid conflicts)
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, name)
    VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'name', ''))
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- =============================================
-- 2. INSTAGRAM ACCOUNTS
-- =============================================
CREATE TABLE IF NOT EXISTS public.instagram_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    session_data TEXT,
    proxy TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    daily_post_limit INT NOT NULL DEFAULT 3,
    posting_schedule JSONB NOT NULL DEFAULT '[10, 14, 19]'::jsonb,
    niche TEXT NOT NULL DEFAULT 'недвижимость',
    city TEXT NOT NULL DEFAULT 'Москва',
    brand_style JSONB NOT NULL DEFAULT '{"bg_color":"#1a1a1a","text_color":"#ffffff","accent_color":"#ff6b35","font_title":"Inter-Bold","font_body":"Inter-Regular"}'::jsonb,
    speaker_photo_url TEXT,
    cta_text TEXT NOT NULL DEFAULT 'Подпишись и получи бонус!',
    cta_keyword TEXT NOT NULL DEFAULT 'КВАРТИРА',
    bio_offer TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_published_at TIMESTAMPTZ
);

ALTER TABLE public.instagram_accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own accounts" ON public.instagram_accounts;
CREATE POLICY "Users manage own accounts"
    ON public.instagram_accounts FOR ALL
    USING (auth.uid() = owner_id);

CREATE INDEX IF NOT EXISTS idx_accounts_owner ON public.instagram_accounts(owner_id);
CREATE INDEX IF NOT EXISTS idx_accounts_active ON public.instagram_accounts(is_active) WHERE is_active = TRUE;

-- =============================================
-- 3. PROPERTY LISTINGS
-- =============================================
CREATE TABLE IF NOT EXISTS public.property_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL CHECK (source IN ('cian', 'avito', 'yandex', 'custom')),
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    price BIGINT NOT NULL,
    price_per_sqm INT,
    area_total NUMERIC(8,2),
    area_living NUMERIC(8,2),
    rooms INT,
    floor INT,
    floors_total INT,
    address TEXT,
    district TEXT,
    metro_station TEXT,
    metro_distance_min INT,
    description TEXT,
    photos JSONB DEFAULT '[]'::jsonb,
    floor_plan_url TEXT,
    special_conditions JSONB DEFAULT '{}'::jsonb,
    developer TEXT,
    complex_name TEXT,
    completion_date TEXT,
    property_class TEXT CHECK (property_class IN ('эконом', 'комфорт', 'бизнес', 'премиум', 'элит')),
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    carousel_generated BOOLEAN NOT NULL DEFAULT FALSE,
    parsed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    created_by UUID REFERENCES public.profiles(id)
);

ALTER TABLE public.property_listings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can read listings" ON public.property_listings;
CREATE POLICY "Authenticated users can read listings"
    ON public.property_listings FOR SELECT
    TO authenticated
    USING (TRUE);

DROP POLICY IF EXISTS "Admins can manage listings" ON public.property_listings;
CREATE POLICY "Admins can manage listings"
    ON public.property_listings FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles
            WHERE id = auth.uid() AND role = 'admin'
        )
    );

CREATE INDEX IF NOT EXISTS idx_listings_featured ON public.property_listings(is_featured) WHERE is_featured = TRUE;
CREATE INDEX IF NOT EXISTS idx_listings_source ON public.property_listings(source);
CREATE INDEX IF NOT EXISTS idx_listings_parsed ON public.property_listings(parsed_at DESC);

-- =============================================
-- 4. CAROUSEL TEMPLATES
-- =============================================
CREATE TABLE IF NOT EXISTS public.carousel_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('topic', 'property')),
    preview_url TEXT,
    style_params JSONB NOT NULL DEFAULT '{"bg_color":"#1a1a1a","text_color":"#ffffff","accent_color":"#ff6b35","font_title":"Inter-Bold","font_body":"Inter-Regular","layout":"speaker_right","overlay_opacity":0.7}'::jsonb,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.carousel_templates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can read templates" ON public.carousel_templates;
CREATE POLICY "Authenticated users can read templates"
    ON public.carousel_templates FOR SELECT
    TO authenticated
    USING (TRUE);

-- =============================================
-- 5. CAROUSELS
-- =============================================
CREATE TABLE IF NOT EXISTS public.carousels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES public.instagram_accounts(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('topic', 'property')),
    listing_id UUID REFERENCES public.property_listings(id) ON DELETE SET NULL,
    template_id UUID REFERENCES public.carousel_templates(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'ready', 'scheduled', 'published', 'failed')),
    slides JSONB NOT NULL DEFAULT '[]'::jsonb,
    caption TEXT,
    hashtags TEXT,
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    instagram_post_id TEXT,
    engagement JSONB DEFAULT '{"likes":0,"comments":0,"saves":0,"shares":0}'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generation_params JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.carousels ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage carousels of own accounts" ON public.carousels;
CREATE POLICY "Users manage carousels of own accounts"
    ON public.carousels FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.instagram_accounts
            WHERE id = carousels.account_id AND owner_id = auth.uid()
        )
    );

CREATE INDEX IF NOT EXISTS idx_carousels_account ON public.carousels(account_id);
CREATE INDEX IF NOT EXISTS idx_carousels_status ON public.carousels(status);
CREATE INDEX IF NOT EXISTS idx_carousels_scheduled ON public.carousels(scheduled_at) WHERE status = 'scheduled';

-- =============================================
-- 6. PUBLISH SCHEDULE
-- =============================================
CREATE TABLE IF NOT EXISTS public.publish_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES public.instagram_accounts(id) ON DELETE CASCADE,
    carousel_id UUID NOT NULL REFERENCES public.carousels(id) ON DELETE CASCADE,
    scheduled_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'publishing', 'published', 'failed')),
    retry_count INT NOT NULL DEFAULT 0,
    error_message TEXT,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.publish_schedules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own schedules" ON public.publish_schedules;
CREATE POLICY "Users manage own schedules"
    ON public.publish_schedules FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.instagram_accounts
            WHERE id = publish_schedules.account_id AND owner_id = auth.uid()
        )
    );

CREATE INDEX IF NOT EXISTS idx_schedules_pending ON public.publish_schedules(scheduled_time)
    WHERE status = 'pending';

-- =============================================
-- 7. CONTENT TOPICS (anti-repeat)
-- =============================================
CREATE TABLE IF NOT EXISTS public.content_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    niche TEXT NOT NULL,
    topic TEXT NOT NULL,
    used_count INT NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    engagement_avg NUMERIC(8,2) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.content_topics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can read topics" ON public.content_topics;
CREATE POLICY "Authenticated users can read topics"
    ON public.content_topics FOR SELECT
    TO authenticated
    USING (TRUE);

CREATE INDEX IF NOT EXISTS idx_topics_niche ON public.content_topics(niche);

-- =============================================
-- Updated_at triggers
-- =============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at ON public.profiles;
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON public.instagram_accounts;
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.instagram_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON public.carousels;
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.carousels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================
-- Seed default templates (only if empty)
-- =============================================
INSERT INTO public.carousel_templates (name, type, style_params, is_default)
SELECT 'Dark Expert', 'topic', '{"bg_color":"#1a1a1a","text_color":"#ffffff","accent_color":"#ff6b35","font_title":"Inter-Bold","font_body":"Inter-Regular","layout":"speaker_right","overlay_opacity":0.7}'::jsonb, TRUE
WHERE NOT EXISTS (SELECT 1 FROM public.carousel_templates WHERE name = 'Dark Expert');

INSERT INTO public.carousel_templates (name, type, style_params, is_default)
SELECT 'Property Offer', 'property', '{"bg_color":"#0d1117","text_color":"#ffffff","accent_color":"#ff4444","font_title":"Inter-Bold","font_body":"Inter-Regular","layout":"fullscreen_bg","overlay_opacity":0.6}'::jsonb, TRUE
WHERE NOT EXISTS (SELECT 1 FROM public.carousel_templates WHERE name = 'Property Offer');

INSERT INTO public.carousel_templates (name, type, style_params, is_default)
SELECT 'Minimal Light', 'topic', '{"bg_color":"#f5f5f5","text_color":"#1a1a1a","accent_color":"#2563eb","font_title":"Inter-Bold","font_body":"Inter-Regular","layout":"speaker_right","overlay_opacity":0.3}'::jsonb, FALSE
WHERE NOT EXISTS (SELECT 1 FROM public.carousel_templates WHERE name = 'Minimal Light');
