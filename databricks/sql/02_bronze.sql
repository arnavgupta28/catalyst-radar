CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}bronze.raw_items (
  content_hash  STRING    NOT NULL COMMENT 'sha256(normalised title | url), de-dup key',
  run_id        STRING,
  source_id     STRING    NOT NULL,
  url           STRING,
  title         STRING,
  summary       STRING,
  outlet        STRING,
  published_at  TIMESTAMP,
  related_count INT       COMMENT 'Pulse: other outlets covering the same story',
  related_urls  ARRAY<STRING>,
  tag           STRING,
  company_hint  STRING,
  payload       STRING    COMMENT 'JSON: source-specific extras',
  fetched_at    TIMESTAMP NOT NULL
)
CLUSTER BY (source_id, fetched_at)
COMMENT 'Every item every source returned (after de-dup)';
