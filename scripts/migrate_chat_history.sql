-- ============================================================
-- Migration: Add conversation history support
-- Recommended architecture: Option 2 (dedicated conversations table)
-- ============================================================

-- 1. Create conversations table
CREATE TABLE IF NOT EXISTS public.conversations (
  id uuid NOT NULL DEFAULT extensions.uuid_generate_v4(),
  user_id text,
  title text NOT NULL DEFAULT 'New Conversation',
  created_at timestamp without time zone DEFAULT now(),
  updated_at timestamp without time zone DEFAULT now(),
  CONSTRAINT conversations_pkey PRIMARY KEY (id)
);

-- 2. Add conversation_id and user_id to chat_history
ALTER TABLE public.chat_history
  ADD COLUMN IF NOT EXISTS conversation_id uuid,
  ADD COLUMN IF NOT EXISTS user_id text;

-- 3. Create index for fast conversation retrieval
CREATE INDEX IF NOT EXISTS idx_chat_history_conversation_id
  ON public.chat_history (conversation_id);

CREATE INDEX IF NOT EXISTS idx_chat_history_created_at
  ON public.chat_history (created_at);

-- 4. Add foreign key constraint (deferrable to avoid migration issues)
ALTER TABLE public.chat_history
  ADD CONSTRAINT IF NOT EXISTS fk_chat_history_conversation_id
  FOREIGN KEY (conversation_id)
  REFERENCES public.conversations (id)
  ON DELETE CASCADE;

-- 5. Migration: Assign existing messages to generated conversations
-- Group by existing session_id (from the old in-memory system)
-- or create one conversation for all orphaned messages
DO $$
DECLARE
  orphaned_count integer;
  migrated_count integer;
  legacy_session_id text;
BEGIN
  SELECT COUNT(*) INTO orphaned_count
  FROM public.chat_history
  WHERE conversation_id IS NULL;

  IF orphaned_count > 0 THEN
    RAISE NOTICE 'Found % orphaned chat_history messages to migrate', orphaned_count;

    -- Group existing messages by their legacy session_id pattern
    -- If session_id was stored elsewhere, adjust this logic accordingly
    -- For now, we create one conversation for all orphaned messages
    INSERT INTO public.conversations (user_id, title, created_at, updated_at)
    SELECT
      NULL,
      'Migrated Conversation',
      MIN(created_at),
      MAX(created_at)
    FROM public.chat_history
    WHERE conversation_id IS NULL
    GROUP BY COALESCE((SELECT session_id FROM conversation_state LIMIT 1), 'legacy-default');

    -- Assign all orphaned messages to the first migrated conversation
    UPDATE public.chat_history
    SET conversation_id = (
      SELECT id FROM public.conversations
      WHERE title = 'Migrated Conversation'
      ORDER BY created_at ASC
      LIMIT 1
    )
    WHERE conversation_id IS NULL;

    GET DIAGNOSTICS migrated_count = ROW_COUNT;
    RAISE NOTICE 'Migrated % messages to conversation history', migrated_count;
  ELSE
    RAISE NOTICE 'No orphaned messages found. Migration already applied.';
  END IF;
END $$;

-- 6. Create updated_at trigger function for conversations
CREATE OR REPLACE FUNCTION update_conversations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_conversations_updated_at ON public.conversations;
CREATE TRIGGER trg_update_conversations_updated_at
  BEFORE UPDATE ON public.conversations
  FOR EACH ROW
  EXECUTE FUNCTION update_conversations_updated_at();

-- ============================================================
-- Verification queries
-- ============================================================

-- Verify conversations table
-- SELECT * FROM public.conversations LIMIT 10;

-- Verify chat_history has conversation_id
-- SELECT id, conversation_id, user_message, created_at FROM public.chat_history LIMIT 10;
