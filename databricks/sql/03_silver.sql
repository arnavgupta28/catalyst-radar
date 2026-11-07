CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}silver.events (
  event_id       STRING NOT NULL,
  content_hash   STRING,
  company_id     STRING NOT NULL,
  source_id      STRING,
  trust          STRING,
  event_type     STRING,
  materiality    INT,
  sentiment_hint STRING,
  reason         STRING,
  title          STRING,
  url            STRING,
  summary        STRING,
  published_at   TIMESTAMP,
  created_at     TIMESTAMP
) CLUSTER BY (company_id, created_at)
COMMENT 'Items that passed triage for a watchlist company';

CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}silver.evidence (
  evidence_id STRING NOT NULL,
  event_id    STRING NOT NULL,
  url         STRING,
  source_id   STRING,
  outlet      STRING,
  excerpt     STRING,
  captured_at TIMESTAMP
) COMMENT 'Sources that support an event (cited by alert facts)';

CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}silver.facts (
  event_id     STRING NOT NULL,
  key          STRING,
  value        STRING,
  verification STRING COMMENT 'confirmed | conflicting | unconfirmed',
  evidence_ids ARRAY<STRING>
) COMMENT 'Facts extracted by the writer model, each tied to evidence';

CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}silver.price_quotes (
  symbol        STRING NOT NULL,
  exchange      STRING,
  currency      STRING,
  price         DOUBLE,
  prev_close    DOUBLE,
  change_pct    DOUBLE,
  day_high      DOUBLE,
  day_low       DOUBLE,
  volume        DOUBLE,
  upper_circuit DOUBLE,
  lower_circuit DOUBLE,
  provider      STRING,
  delayed       BOOLEAN,
  ts            TIMESTAMP
) CLUSTER BY (symbol, ts)
COMMENT 'Quote snapshots from price providers';
