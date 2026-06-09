-- Migration script to update existing chat tables to new schema
-- Run this if you already have ChatSessions and ChatMessages tables

-- Add new columns to ChatSessions if they don't exist
DO $$ 
BEGIN
    -- Add user_id column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ChatSessions' AND column_name='user_id') THEN
        ALTER TABLE public."ChatSessions" ADD COLUMN user_id TEXT DEFAULT 'default_user';
    END IF;
    
    -- Add last_message_at column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ChatSessions' AND column_name='last_message_at') THEN
        ALTER TABLE public."ChatSessions" ADD COLUMN last_message_at TIMESTAMPTZ;
    END IF;
    
    -- Add message_count column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ChatSessions' AND column_name='message_count') THEN
        ALTER TABLE public."ChatSessions" ADD COLUMN message_count INTEGER DEFAULT 0;
    END IF;
    
    -- Set default for title if it doesn't have one
    ALTER TABLE public."ChatSessions" ALTER COLUMN title SET DEFAULT 'New Chat';
END $$;

-- Add user_id column to ChatMessages if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='ChatMessages' AND column_name='user_id') THEN
        ALTER TABLE public."ChatMessages" ADD COLUMN user_id TEXT DEFAULT 'default_user';
    END IF;
END $$;

-- Add role constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage 
        WHERE table_name = 'ChatMessages' AND constraint_name LIKE '%role%check%'
    ) THEN
        ALTER TABLE public."ChatMessages" ADD CONSTRAINT chatmessages_role_check 
        CHECK (role IN ('user', 'assistant'));
    END IF;
END $$;

-- Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON public."ChatMessages"(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON public."ChatSessions"(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON public."ChatSessions"(updated_at DESC);

-- Update message counts for existing sessions
UPDATE public."ChatSessions" s
SET message_count = (
    SELECT COUNT(*) 
    FROM public."ChatMessages" m 
    WHERE m.session_id = s.id
)
WHERE message_count = 0 OR message_count IS NULL;

-- Update last_message_at for existing sessions
UPDATE public."ChatSessions" s
SET last_message_at = (
    SELECT MAX(created_at) 
    FROM public."ChatMessages" m 
    WHERE m.session_id = s.id
)
WHERE last_message_at IS NULL;

-- Create or replace the trigger function
CREATE OR REPLACE FUNCTION update_session_on_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public."ChatSessions"
    SET 
        updated_at = NOW(),
        last_message_at = NEW.created_at,
        message_count = message_count + 1
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if it exists and recreate it
DROP TRIGGER IF EXISTS trigger_update_session_on_message ON public."ChatMessages";

CREATE TRIGGER trigger_update_session_on_message
    AFTER INSERT ON public."ChatMessages"
    FOR EACH ROW
    EXECUTE FUNCTION update_session_on_message();

-- Update titles for sessions that don't have one
UPDATE public."ChatSessions"
SET title = 'New Chat'
WHERE title IS NULL OR title = '';

COMMIT;
