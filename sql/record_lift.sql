-- One row per record constraint a user lifted, with confirmation, in one chat session (MV5). Shared by schema.sql
-- (a fresh volume) and migrations/009-record-lift.sql.
CREATE TABLE IF NOT EXISTS session_record_lift (
  session_id     uuid NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
  constraint_id  text NOT NULL,          -- allergen:<group> | ingredient:<name> | nutrient:<column> | soft:<column>
  reason         text,                   -- what the user gave in the interface, if anything
  confirmed_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (session_id, constraint_id)
);
