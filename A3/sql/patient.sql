-- Patient records read vectorless (docs/plan/A3_vectorless_ho_so.md 5.7). Written by scripts/patient_ingest.py from
-- Synthea C-CDA files; never edited by hand. Shared by schema.sql (a fresh volume) and migrations/007-patient.sql
-- (an existing one). No name, address, race or P7 content is stored; source_file holds Synthea's fake name and is
-- never returned by the API.

CREATE TABLE IF NOT EXISTS patient (
  patient_id       text PRIMARY KEY,                -- Synthea uuid (patientRole/id/@extension)
  source           text NOT NULL CHECK (source IN ('sample', 'generated')),
  source_dir       text NOT NULL,
  source_file      text NOT NULL,
  sex              text,
  age_years        integer,                         -- at record_date
  record_date      date NOT NULL,                   -- ClinicalDocument/effectiveTime, never the clock
  deceased         boolean NOT NULL DEFAULT false,  -- loaded and counted (P1), left out of the P8 evaluation set
  synthea_version  text,
  loaded_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS patient_node (
  patient_id      text NOT NULL REFERENCES patient(patient_id) ON DELETE CASCADE,
  node_id         text NOT NULL,                    -- patient:<uuid>, allergies, results.2021 ...
  parent_id       text,
  kind            text NOT NULL CHECK (kind IN ('root', 'fixed', 'context')),
  title           text NOT NULL,
  summary         text,                             -- context nodes (V1c)
  summary_source  text CHECK (summary_source IN ('template', 'llm')),
  facts           jsonb NOT NULL,
  entry_ids       text[] NOT NULL,
  position        smallint NOT NULL,                -- order in the tree
  PRIMARY KEY (patient_id, node_id)
);

CREATE TABLE IF NOT EXISTS patient_profile_cache (
  patient_id       text NOT NULL REFERENCES patient(patient_id) ON DELETE CASCADE,
  ruleset_version  text NOT NULL,
  mode             text NOT NULL,
  profile          jsonb NOT NULL,
  built_at         timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (patient_id, ruleset_version, mode)
);

-- A chat session may be about one patient; its constraints may come from the record (scope 'patient', MV3).
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS patient_id text REFERENCES patient(patient_id);
ALTER TABLE session_constraint
  ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'dialogue' CHECK (source IN ('dialogue', 'patient')),
  ADD COLUMN IF NOT EXISTS evidence jsonb;
ALTER TABLE session_constraint DROP CONSTRAINT IF EXISTS session_constraint_scope_check;
ALTER TABLE session_constraint ADD CONSTRAINT session_constraint_scope_check
  CHECK (scope IN ('session', 'turn', 'patient'));
