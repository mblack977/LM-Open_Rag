DROP TABLE IF EXISTS public."ChatMessages" CASCADE;
DROP TABLE IF EXISTS public."ChatSessions" CASCADE;

CREATE TABLE public."ChatSessions" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT DEFAULT 'default_user',
    title TEXT DEFAULT 'New Chat',
    collection TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0
);

CREATE TABLE public."ChatMessages" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES public."ChatSessions"(id) ON DELETE CASCADE,
    user_id TEXT DEFAULT 'default_user',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB,
    retrieval_profile TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_messages_session_id ON public."ChatMessages"(session_id);
CREATE INDEX idx_chat_messages_user_id ON public."ChatMessages"(user_id);
CREATE INDEX idx_chat_sessions_user_id ON public."ChatSessions"(user_id);
CREATE INDEX idx_chat_sessions_updated_at ON public."ChatSessions"(updated_at DESC);

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

CREATE TRIGGER trigger_update_session_on_message
    AFTER INSERT ON public."ChatMessages"
    FOR EACH ROW
    EXECUTE FUNCTION update_session_on_message();

GRANT ALL ON public."ChatSessions" TO authenticator, service_role, anon;
GRANT ALL ON public."ChatMessages" TO authenticator, service_role, anon;
