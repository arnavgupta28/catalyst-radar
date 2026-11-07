CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}ops.source_runs (
  run_id     STRING,
  source_id  STRING,
  started_at TIMESTAMP,
  items      INT,
  new_items  INT,
  errors     STRING COMMENT 'JSON list'
) COMMENT 'One row per source per pipeline run (drives "is it due?")';

CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}ops.usage_events (
  ts       TIMESTAMP,
  provider STRING,
  metric   STRING,
  `count`  INT
) COMMENT 'API usage (TinyFish search/fetch, LLM calls) vs free limits';

-- Config mirrored from config/*.yaml by 00_setup (for dashboards and the website)
CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}ops.companies (
  id STRING, name STRING, aliases ARRAY<STRING>, sector STRING, industry STRING, asset_class STRING
);
CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}ops.listings (
  company_id STRING, exchange STRING, symbol STRING, currency STRING, yahoo STRING, cik STRING
);
CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}ops.sources (
  id STRING, name STRING, market STRING, url STRING, parser STRING, method STRING, trust STRING,
  `interval` STRING, active_hours STRING, scope STRING, exchange STRING, tag STRING,
  enabled BOOLEAN, builtin BOOLEAN
);

CREATE OR REPLACE VIEW ${catalog}.${prefix}ops.v_usage_today AS
SELECT provider, metric, sum(`count`) AS used
FROM ${catalog}.${prefix}ops.usage_events
WHERE ts >= current_date()
GROUP BY provider, metric;

CREATE OR REPLACE VIEW ${catalog}.${prefix}ops.v_source_health AS
SELECT source_id,
       max(started_at)                                  AS last_run,
       sum(items)                                       AS items_7d,
       sum(new_items)                                   AS new_7d,
       sum(CASE WHEN errors <> '[]' THEN 1 ELSE 0 END)  AS runs_with_errors_7d
FROM ${catalog}.${prefix}ops.source_runs
WHERE started_at >= current_date() - INTERVAL 7 DAYS
GROUP BY source_id;
