-- I13 interactive Learn: persist owner Learn after bounded proof admission is stopped.
ALTER TABLE i13_processing_admissions
  ADD COLUMN IF NOT EXISTS interactive_learn_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS interactive_learn_ref TEXT;
