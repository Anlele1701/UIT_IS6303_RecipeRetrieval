-- One row per lift a user confirmed in one chat session (MV5): a single record constraint, or a whole record group
-- (every constraint one allergy entry yields; ADR-0008). Shared by schema.sql (a fresh volume) and migrations 009-010.
CREATE TABLE IF NOT EXISTS session_record_lift (
  session_id     uuid NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
  constraint_id  text NOT NULL,          -- allergen:<group> | ingredient:<name> | nutrient:<column> | soft:<column>
                                         -- | record:allergy/<SNOMED code> (a group)
  reason         text,                   -- what the user gave in the interface, if anything
  confirmed_at   timestamptz NOT NULL DEFAULT now(),
  members        text[] NOT NULL DEFAULT '{}',  -- the constraint ids this lift took out (a single one: itself)
  PRIMARY KEY (session_id, constraint_id)
);
ALTER TABLE session_record_lift ADD COLUMN IF NOT EXISTS members text[] NOT NULL DEFAULT '{}';
