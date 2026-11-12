#!/bin/sh
set -eu
# Only runs on FIRST creation of this dedicated volume. Never print SQL/secrets.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv app_password ACCOUNTS_DB_PASSWORD
\getenv migrator_password ACCOUNTS_DB_MIGRATOR_PASSWORD
CREATE ROLE titan_accounts_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
SELECT format('CREATE ROLE titan_accounts_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'app_password') \gexec
SELECT format('CREATE ROLE titan_accounts_migrator LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION IN ROLE titan_accounts_owner PASSWORD %L', :'migrator_password') \gexec
ALTER DATABASE titan_accounts OWNER TO titan_accounts_owner;
ALTER SCHEMA public OWNER TO titan_accounts_owner;
REVOKE ALL ON DATABASE titan_accounts FROM PUBLIC;
GRANT CONNECT ON DATABASE titan_accounts TO titan_accounts_app, titan_accounts_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO titan_accounts_app;
ALTER DEFAULT PRIVILEGES FOR ROLE titan_accounts_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO titan_accounts_app;
ALTER DEFAULT PRIVILEGES FOR ROLE titan_accounts_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO titan_accounts_app;
SQL
