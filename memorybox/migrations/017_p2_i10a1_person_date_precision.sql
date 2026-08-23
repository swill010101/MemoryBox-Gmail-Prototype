-- P2-I10A.1: birth/death date precision (year / month / day).
-- Existing rows default to day. Unknown remains "no confirmed fact row".

ALTER TABLE person_facts
    ADD COLUMN IF NOT EXISTS date_precision TEXT NOT NULL DEFAULT 'day';

ALTER TABLE person_facts
    DROP CONSTRAINT IF EXISTS person_facts_date_precision_check;

ALTER TABLE person_facts
    ADD CONSTRAINT person_facts_date_precision_check
    CHECK (date_precision IN ('day', 'month', 'year', 'unknown'));
