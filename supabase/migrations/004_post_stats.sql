-- =============================================
-- 004: Post Stats — engagement tracking
-- Stores likes, comments, reach, saves per post
-- Safe to re-run (IF NOT EXISTS)
-- =============================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'post_stats') THEN
        CREATE TABLE public.post_stats (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            carousel_id UUID NOT NULL REFERENCES public.carousels(id) ON DELETE CASCADE,
            account_id UUID NOT NULL REFERENCES public.instagram_accounts(id) ON DELETE CASCADE,
            media_id TEXT,              -- Instagram media PK
            media_code TEXT,            -- Instagram shortcode (for URL)

            -- Engagement metrics
            likes INTEGER NOT NULL DEFAULT 0,
            comments INTEGER NOT NULL DEFAULT 0,
            saves INTEGER NOT NULL DEFAULT 0,
            shares INTEGER NOT NULL DEFAULT 0,
            reach INTEGER NOT NULL DEFAULT 0,
            impressions INTEGER NOT NULL DEFAULT 0,

            -- Calculated
            engagement_rate NUMERIC(5,2) DEFAULT 0,  -- (likes+comments+saves) / reach * 100

            -- Timestamps
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            published_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_post_stats_carousel ON public.post_stats(carousel_id);
        CREATE INDEX idx_post_stats_account ON public.post_stats(account_id);
        CREATE INDEX idx_post_stats_fetched ON public.post_stats(fetched_at DESC);
        CREATE UNIQUE INDEX idx_post_stats_unique ON public.post_stats(carousel_id, account_id);
    END IF;
END $$;

ALTER TABLE public.post_stats ENABLE ROW LEVEL SECURITY;

-- RLS: users can see stats for their own accounts
DROP POLICY IF EXISTS "Users see own stats" ON public.post_stats;
CREATE POLICY "Users see own stats"
    ON public.post_stats FOR SELECT
    USING (
        account_id IN (
            SELECT id FROM public.instagram_accounts WHERE owner_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Service can insert stats" ON public.post_stats;
CREATE POLICY "Service can insert stats"
    ON public.post_stats FOR INSERT
    WITH CHECK (true);

DROP POLICY IF EXISTS "Service can update stats" ON public.post_stats;
CREATE POLICY "Service can update stats"
    ON public.post_stats FOR UPDATE
    USING (true);

-- Add media_id column to carousels if missing (for linking published posts)
DO $$
BEGIN
    BEGIN ALTER TABLE public.carousels ADD COLUMN media_id TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END;
    BEGIN ALTER TABLE public.carousels ADD COLUMN media_code TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END;
END $$;
