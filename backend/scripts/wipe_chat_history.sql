-- One-shot wipe of chat history and attachments (non-production).
-- Do NOT run through Alembic. Manual:
--   psql "$DATABASE_URL" -f backend/scripts/wipe_chat_history.sql
--
-- Also delete local blobs:
--   rm -rf backend/data/chat-attachments
-- And, if using Vercel Blob, remove the `chat-attachments/` prefix in the blob store.

BEGIN;

-- chat_attachments.message_id -> messages; both cascade from chats.
-- Delete children first in case an environment lacks ON DELETE CASCADE.
DELETE FROM chat_attachments;
DELETE FROM messages;
DELETE FROM chats;

COMMIT;
