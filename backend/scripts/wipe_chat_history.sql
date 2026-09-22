-- One-shot wipe of chat history and attachments (non-production).
-- Manual: psql "$DATABASE_URL" -f backend/scripts/wipe_chat_history.sql
--
-- Also clear Redis:
--   redis-cli KEYS 'session:*' | xargs redis-cli DEL
--   redis-cli KEYS '*chat*|*'  # scoped MAF history keys under chat prefix

BEGIN;

DELETE FROM chat_attachments;
DELETE FROM chat_events;
DELETE FROM chats;

COMMIT;
