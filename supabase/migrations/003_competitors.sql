-- ═══════════════════════════════════════════════════════════════════
-- Migration 003: Competitor tracking tables
-- Run in Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════════════

-- Saved competitor accounts
CREATE TABLE IF NOT EXISTS competitor_accounts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    platform TEXT DEFAULT 'instagram',
    notes TEXT,
    followers INTEGER,
    bio TEXT,
    posts_count INTEGER,
    last_scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(owner_id, username)
);

-- Competitor analysis results (history)
CREATE TABLE IF NOT EXISTS competitor_analyses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    competitor_username TEXT,
    posts_count INTEGER DEFAULT 0,
    analysis JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS policies
ALTER TABLE competitor_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitor_analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own competitors" ON competitor_accounts
    FOR ALL USING (auth.uid() = owner_id);

CREATE POLICY "Users can manage own analyses" ON competitor_analyses
    FOR ALL USING (auth.uid() = owner_id);

-- Service role bypass
CREATE POLICY "Service role full access competitors" ON competitor_accounts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access analyses" ON competitor_analyses
    FOR ALL USING (auth.role() = 'service_role');

-- Indexes
CREATE INDEX IF NOT EXISTS idx_competitor_accounts_owner ON competitor_accounts(owner_id);
CREATE INDEX IF NOT EXISTS idx_competitor_analyses_owner ON competitor_analyses(owner_id);
