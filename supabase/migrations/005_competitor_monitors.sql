-- Competitor monitor accounts for auto-rewrite
CREATE TABLE IF NOT EXISTS public.competitor_monitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL,
    username TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    auto_rewrite BOOLEAN NOT NULL DEFAULT true,
    lead_magnet TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(owner_id, username)
);

-- RLS
ALTER TABLE public.competitor_monitors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own monitors"
    ON public.competitor_monitors FOR ALL
    USING (owner_id = auth.uid());

-- Design settings table
CREATE TABLE IF NOT EXISTS public.design_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL UNIQUE,
    template_id TEXT NOT NULL DEFAULT 'expert',
    bg_type TEXT NOT NULL DEFAULT 'template',
    bg_color TEXT DEFAULT '#0a0a0a',
    bg_gradient_start TEXT,
    bg_gradient_end TEXT,
    bg_upload_path TEXT,
    font_pairing TEXT NOT NULL DEFAULT 'luxury',
    title_size INT DEFAULT 62,
    body_size INT DEFAULT 36,
    text_color TEXT DEFAULT '#ffffff',
    accent_color TEXT DEFAULT '#d4a853',
    text_position TEXT DEFAULT 'bottom',
    image_position TEXT DEFAULT 'top',
    avatar_placement TEXT DEFAULT 'middle',
    canvas_width INT DEFAULT 1080,
    canvas_height INT DEFAULT 1350,
    photo_type TEXT DEFAULT 'expert',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.design_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own design settings"
    ON public.design_settings FOR ALL
    USING (owner_id = auth.uid());
