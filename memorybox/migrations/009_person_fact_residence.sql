-- Compact About “Lives in” — residence fact on person_facts (I5 Person Explorer).

ALTER TABLE person_facts DROP CONSTRAINT IF EXISTS person_facts_fact_kind_check;
ALTER TABLE person_facts DROP CONSTRAINT IF EXISTS person_facts_check;

ALTER TABLE person_facts ADD CONSTRAINT person_facts_fact_kind_check
    CHECK (fact_kind IN ('birth_date', 'death_date', 'note', 'residence'));

ALTER TABLE person_facts ADD CONSTRAINT person_facts_value_check
    CHECK (
        (fact_kind IN ('birth_date', 'death_date') AND value_date IS NOT NULL)
        OR (
            fact_kind IN ('note', 'residence')
            AND value_text IS NOT NULL
            AND length(trim(value_text)) > 0
        )
    );
