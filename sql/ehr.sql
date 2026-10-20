-- Patient records (Synthea) for the vectorless side of the pipeline. Separate schema:
-- nothing here touches recipe / chunk (ADR-0001's "chunk is rebuilt only" is unaffected).
--
-- The live volume does not re-run docker-init.sql, so apply this once by hand:
--   psql postgresql://recipe:recipe@localhost:5434/recipe -v ON_ERROR_STOP=1 -f sql/ehr.sql
-- It is safe to run again: it only creates what is missing.
--
-- All data is synthetic (Synthea). Conditions are matched by `code`, never by `description`.

CREATE SCHEMA IF NOT EXISTS ehr;

-- One row per load of a Synthea cohort, so the DB says where its data came from.
CREATE TABLE IF NOT EXISTS ehr.cohort_run (
  run_id          text PRIMARY KEY,
  reference_date  date NOT NULL,         -- the simulation's "today": latest condition start in the load
  manifest        jsonb NOT NULL,        -- source dir, Synthea arguments, file hashes, row counts
  loaded_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ehr.patient (
  id            uuid PRIMARY KEY,        -- Synthea Id
  run_id        text NOT NULL REFERENCES ehr.cohort_run(run_id),
  birth_date    date NOT NULL,
  gender        char(1) NOT NULL,
  display_name  text NOT NULL            -- Synthea's invented name, display only
);

CREATE TABLE IF NOT EXISTS ehr.condition (
  patient_id   uuid NOT NULL REFERENCES ehr.patient(id) ON DELETE CASCADE,
  start_date   date NOT NULL,
  stop_date    date,                     -- NULL = still active
  system       text NOT NULL,            -- SNOMED-CT in every Synthea row
  code         text NOT NULL,
  description  text NOT NULL
);
CREATE INDEX IF NOT EXISTS condition_patient_idx ON ehr.condition (patient_id);
CREATE INDEX IF NOT EXISTS condition_code_idx ON ehr.condition (code);

CREATE TABLE IF NOT EXISTS ehr.medication (
  patient_id          uuid NOT NULL REFERENCES ehr.patient(id) ON DELETE CASCADE,
  start_at            timestamptz NOT NULL,
  stop_at             timestamptz,
  code                text NOT NULL,     -- RxNorm
  description         text NOT NULL,
  reason_code         text,              -- SNOMED, joins to condition.code
  reason_description  text
);
CREATE INDEX IF NOT EXISTS medication_patient_idx ON ehr.medication (patient_id);

-- Only a whitelist of LOINC codes (see scripts/load_synthea.py); the full file is ~1.2M rows.
CREATE TABLE IF NOT EXISTS ehr.observation (
  patient_id   uuid NOT NULL REFERENCES ehr.patient(id) ON DELETE CASCADE,
  observed_at  timestamptz NOT NULL,
  code         text NOT NULL,            -- LOINC
  description  text NOT NULL,
  value_num    numeric,                  -- NULL when the value is text
  value_text   text,
  units        text
);
CREATE INDEX IF NOT EXISTS observation_patient_code_idx ON ehr.observation (patient_id, code, observed_at DESC);

-- Food allergies are screened against Recipe titles and ingredient lines (api/allergens.py).
CREATE TABLE IF NOT EXISTS ehr.allergy (
  patient_id   uuid NOT NULL REFERENCES ehr.patient(id) ON DELETE CASCADE,
  start_date   date NOT NULL,
  stop_date    date,
  code         text NOT NULL,
  description  text NOT NULL,
  category     text                      -- food / medication / environment
);
CREATE INDEX IF NOT EXISTS allergy_patient_idx ON ehr.allergy (patient_id);

-- Derived data, rebuilt by scripts/render_ehr_documents.py and never edited by hand: each patient's record
-- as one Markdown document, for the vectorless (tree navigation) branch. Only the evaluation reads it;
-- /recommend decides from the tables above.
CREATE TABLE IF NOT EXISTS ehr.record_document (
  patient_id   uuid PRIMARY KEY REFERENCES ehr.patient(id) ON DELETE CASCADE,
  markdown     text NOT NULL,
  rendered_at  timestamptz NOT NULL DEFAULT now()
);
