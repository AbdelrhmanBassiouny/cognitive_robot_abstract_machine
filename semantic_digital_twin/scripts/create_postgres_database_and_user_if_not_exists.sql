-- create_postgres_database_and_user_if_not_exists.sql (PostgreSQL, idempotent, psql-compatible)
--
-- Must run as a PostgreSQL superuser: psql connects as the operating-system user by
-- default, and that user normally has no database role ("FATAL: role ... does not
-- exist"). Feed the script through standard input rather than -f, since the postgres
-- system user usually cannot read a file inside another user's home directory.
--
-- Usage, from the workspace root:
--   sudo -u postgres psql \
--     -v db_name="semantic_digital_twin" \
--     -v user_name="semantic_digital_twin" \
--     -v user_password="a_strong_password_here" \
--     < semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql
--
-- Every -v variable is optional; the defaults below are used for any that is not given.

-- 0) Defaults for the variables the caller did not set
\if :{?db_name}
\else
  \set db_name semantic_digital_twin
\endif
\if :{?user_name}
\else
  \set user_name semantic_digital_twin
\endif
\if :{?user_password}
\else
  \set user_password montessori
\endif

-- 1) Create database if it does not exist (PostgreSQL has no CREATE DATABASE IF NOT EXISTS)
SELECT 'CREATE DATABASE ' || quote_ident(:'db_name')
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = :'db_name'
)\gexec

-- 2) Create role (user) if it does not exist
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'user_name', :'user_password')
WHERE NOT EXISTS (
  SELECT FROM pg_roles WHERE rolname = :'user_name'
)\gexec

-- 3) Make that role the owner of the database
ALTER DATABASE :"db_name" OWNER TO :"user_name";

-- 4) Connect to the target database as current superuser (not the new user),
--    so we can set permissions and default privileges inside that database
\c :"db_name"

-- 5) Grant privileges on the public schema to the application role
GRANT ALL ON SCHEMA public TO :"user_name";

-- 6) Ensure future objects get privileges automatically
--    Use FOR ROLE to set defaults owned by the application role
ALTER DEFAULT PRIVILEGES FOR ROLE :"user_name" IN SCHEMA public GRANT ALL ON TABLES TO :"user_name";
ALTER DEFAULT PRIVILEGES FOR ROLE :"user_name" IN SCHEMA public GRANT ALL ON SEQUENCES TO :"user_name";
ALTER DEFAULT PRIVILEGES FOR ROLE :"user_name" IN SCHEMA public GRANT ALL ON FUNCTIONS TO :"user_name";
