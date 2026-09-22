-- One-shot wipe of chat history and attachments (non-production).
-- Prefer Alembic revision 032 (upgrade head) for the same effect in dev.
-- Manual fallback: psql "$DATABASE_URL" -f backend/scripts/wipe_chat_history.sql
--
-- Also clear Redis session hot cache:
--   cd backend && python scripts/clear_redis_session_cache.py

BEGIN;

DELETE FROM chat_attachments;
DELETE FROM chat_ui_annotations;
DELETE FROM chat_messages;
DELETE FROM chat_runs;
DELETE FROM chats;

COMMIT;
