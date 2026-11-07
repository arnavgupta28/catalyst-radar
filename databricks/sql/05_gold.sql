CREATE TABLE IF NOT EXISTS ${catalog}.${prefix}gold.alerts (
  alert_id       STRING NOT NULL,
  event_id       STRING NOT NULL,
  company_id     STRING NOT NULL,
  market         STRING,
  priority       STRING,
  sentiment      STRING,
  headline       STRING,
  what_happened  STRING,
  why_it_matters STRING,
  risks          STRING,
  bull_case      STRING,
  bear_case      STRING,
  next_steps     STRING,
  source_url     STRING,
  mode           STRING COMMENT 'live | local | mock',
  model          STRING,
  created_at     TIMESTAMP,
  body           STRING COMMENT 'Full alert JSON (facts + evidence)'
) CLUSTER BY (created_at)
COMMENT 'Finished alerts: research, not investment advice';

CREATE OR REPLACE VIEW ${catalog}.${prefix}gold.v_latest_quotes AS
SELECT * EXCEPT (rn) FROM (
  SELECT q.*, row_number() OVER (PARTITION BY symbol, exchange ORDER BY ts DESC) AS rn
  FROM ${catalog}.${prefix}silver.price_quotes q
) WHERE rn = 1;

CREATE OR REPLACE VIEW ${catalog}.${prefix}gold.v_feed AS
SELECT a.alert_id, a.created_at, a.market, a.priority, a.sentiment, a.headline, a.why_it_matters,
       a.company_id, c.name AS company, c.sector, c.asset_class, a.source_url, a.mode
FROM ${catalog}.${prefix}gold.alerts a
LEFT JOIN ${catalog}.${prefix}ops.companies c ON c.id = a.company_id;
