-- Conversation state, traces and feedback for the chat pipeline (api/pipeline). Shared by schema.sql (a fresh
-- volume) and migrations/005-chat.sql (an existing one). Sessions are local and can be deleted at any time.

CREATE TABLE IF NOT EXISTS chat_session (
  id          uuid PRIMARY KEY,
  created_at  timestamptz NOT NULL DEFAULT now(),
  lang        text,                   -- language of the first message
  preset      text NOT NULL DEFAULT 'S'  -- api/pipeline/flags.py preset the session runs
);

CREATE TABLE IF NOT EXISTS chat_message (
  id          bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  session_id  uuid NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
  role        text NOT NULL CHECK (role IN ('user', 'assistant')),
  content     text NOT NULL,
  lang        text,
  recipe_ids  integer[] NOT NULL DEFAULT '{}',  -- assistant turn: Recipes shown, in order (for "món thứ 2")
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_message_session_idx ON chat_message (session_id, id);

-- The constraints the session currently applies (M2). The UI chips edit these rows (PATCH, milestone M4).
CREATE TABLE IF NOT EXISTS session_constraint (
  id                 bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  session_id         uuid NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
  type               text NOT NULL CHECK (type IN ('allergen', 'ingredient_exclude', 'ingredient_include', 'diet',
                                                   'max_total_minutes', 'max_calories', 'category')),
  value              text NOT NULL,
  scope              text NOT NULL CHECK (scope IN ('session', 'turn')),
  source_message_id  bigint REFERENCES chat_message(id) ON DELETE SET NULL,
  active             boolean NOT NULL DEFAULT true,
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS session_constraint_session_idx ON session_constraint (session_id) WHERE active;

-- One row per pipeline stage per assistant turn: governance and error analysis (sườn 3.3, 4.8).
CREATE TABLE IF NOT EXISTS retrieval_trace (
  id          bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  message_id  bigint NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
  stage       text NOT NULL,           -- m1 .. m7
  payload     jsonb NOT NULL,
  latency_ms  real NOT NULL
);
CREATE INDEX IF NOT EXISTS retrieval_trace_message_idx ON retrieval_trace (message_id);

CREATE TABLE IF NOT EXISTS feedback (
  id          bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  message_id  bigint NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
  rating      smallint NOT NULL CHECK (rating IN (-1, 1)),
  comment     text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
