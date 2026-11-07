-- Catalyst Radar: schemas + landing volume.
-- ${catalog} and ${prefix} are filled in by databricks/notebooks/00_setup.py
-- (catalog = catalyst, prefix = ''   or   catalog = workspace, prefix = 'catalyst_').

CREATE SCHEMA IF NOT EXISTS ${catalog}.${prefix}bronze COMMENT 'Raw items exactly as sources said them';
CREATE SCHEMA IF NOT EXISTS ${catalog}.${prefix}silver COMMENT 'Events, evidence, facts, price quotes';
CREATE SCHEMA IF NOT EXISTS ${catalog}.${prefix}gold   COMMENT 'Alerts and views the app reads';
CREATE SCHEMA IF NOT EXISTS ${catalog}.${prefix}ops    COMMENT 'Config, source runs, usage counters';

CREATE VOLUME IF NOT EXISTS ${catalog}.${prefix}bronze.landing
  COMMENT 'Files pushed in from outside (backup fetcher, simulation dataset)';
