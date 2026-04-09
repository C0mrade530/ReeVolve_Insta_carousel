-- Migration 002: Make carousels work without instagram_accounts binding
-- Adds owner_id, makes account_id nullable, adds "generating" status

-- 1. Add owner_id column
ALTER TABLE public.carousels
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id);

-- 2. Make account_id nullable
ALTER TABLE public.carousels
    ALTER COLUMN account_id DROP NOT NULL;

-- 3. Drop old status constraint and add new one with "generating"
ALTER TABLE public.carousels
    DROP CONSTRAINT IF EXISTS carousels_status_check;

ALTER TABLE public.carousels
    ADD CONSTRAINT carousels_status_check
    CHECK (status IN ('draft', 'generating', 'ready', 'scheduled', 'published', 'failed'));

-- 4. Backfill owner_id from existing carousels
UPDATE public.carousels c
SET owner_id = ia.owner_id
FROM public.instagram_accounts ia
WHERE c.account_id = ia.id
  AND c.owner_id IS NULL;

-- 5. Update RLS policy
DROP POLICY IF EXISTS "Users can manage own carousels" ON public.carousels;

CREATE POLICY "Users can manage own carousels" ON public.carousels
    FOR ALL
    USING (
        owner_id = auth.uid()
        OR account_id IN (
            SELECT id FROM public.instagram_accounts WHERE owner_id = auth.uid()
        )
    );

-- 6. Index on owner_id
CREATE INDEX IF NOT EXISTS idx_carousels_owner_id ON public.carousels(owner_id);

-- 7. Make publish_schedules.account_id nullable too
ALTER TABLE public.publish_schedules
    ALTER COLUMN account_id DROP NOT NULL;
