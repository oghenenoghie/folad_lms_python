-- Creates the non-superuser role the application connects as, and makes it
-- the owner of the application database.
--
-- Why: the postgres image makes its own POSTGRES_USER a superuser, and
-- superusers bypass Row-Level Security entirely, so an app connected as
-- one never exercises the tenant_isolation policies (layer 3 of §7
-- docs/ARCHITECTURE.md). This role gets LOGIN + CREATEDB (pytest-django
-- creates and drops test_<db>) and nothing else: no SUPERUSER, no
-- BYPASSRLS. It owns the database, so `migrate` can run the DDL that RLS
-- migrations need (ALTER TABLE ... ENABLE/FORCE ROW LEVEL SECURITY,
-- CREATE POLICY require table ownership). FORCE ROW LEVEL SECURITY then
-- applies the policies to that owner too. This mirrors the role that
-- .github/workflows/backend-ci.yml creates for the test suite.
--
-- When it runs: automatically, once, when docker-compose's postgres
-- service initialises an empty `postgres_data` volume. The postgres
-- image's entrypoint runs it as the bootstrap superuser.
--
-- Re-running it is safe, and is also how to retrofit an existing database:
-- it creates or updates the role, then hands it ownership of the database
-- and of any tables, views, sequences and functions in `public` that
-- `migrate` already created as the superuser. See docs/README.md,
-- "Database roles", for the commands.
--
-- Inputs: psql variables app_user / app_password (`-v app_user=...`),
-- falling back to the APP_DB_USER / APP_DB_PASSWORD environment variables
-- that docker-compose.yml passes to the postgres service. Connect to the
-- application database (POSTGRES_DB) as a superuser to run it.

\if :{?app_user}
\else
  \getenv app_user APP_DB_USER
\endif
\if :{?app_password}
\else
  \getenv app_password APP_DB_PASSWORD
\endif
\if :{?app_user}
\else
  \set app_user ''
\endif
\if :{?app_password}
\else
  \set app_password ''
\endif

BEGIN;

-- Hand the psql variables to the DO block below through transaction-local
-- settings, since psql does not interpolate variables inside $$ bodies.
SET LOCAL sms_init.app_user = :'app_user';
SET LOCAL sms_init.app_password = :'app_password';

DO $$
DECLARE
    app_user     text := current_setting('sms_init.app_user');
    app_password text := current_setting('sms_init.app_password');
    app_oid      oid;
    obj          record;
BEGIN
    IF app_user = '' OR app_password = '' THEN
        RAISE EXCEPTION 'APP_DB_USER and APP_DB_PASSWORD (or -v app_user=... -v app_password=...) must both be set';
    END IF;

    -- The bootstrap superuser (oid 10) can never lose SUPERUSER, so it can
    -- never be the RLS-restricted app role. This trips on databases whose
    -- only role is the old superuser `sms`: pick a different app role name.
    IF app_user = current_user
       OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_user AND oid = 10) THEN
        RAISE EXCEPTION 'App role "%" must not be the bootstrap superuser: superusers bypass Row-Level Security. Use a separate role (default sms_app) and point POSTGRES_USER at it.', app_user;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_user) THEN
        EXECUTE format(
            'ALTER ROLE %I WITH LOGIN CREATEDB NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOREPLICATION PASSWORD %L',
            app_user, app_password
        );
    ELSE
        EXECUTE format(
            'CREATE ROLE %I WITH LOGIN CREATEDB NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOREPLICATION PASSWORD %L',
            app_user, app_password
        );
    END IF;
    SELECT oid INTO app_oid FROM pg_roles WHERE rolname = app_user;

    EXECUTE format('ALTER DATABASE %I OWNER TO %I', current_database(), app_user);

    -- On clusters initialised by Postgres 15+, `public` is owned by
    -- pg_database_owner and so follows the database owner already. Older,
    -- pg_upgrade'd clusters may still have the superuser owning it.
    IF (SELECT nspowner FROM pg_namespace WHERE nspname = 'public')
       NOT IN ('pg_database_owner'::regrole, app_oid) THEN
        EXECUTE format('ALTER SCHEMA public OWNER TO %I', app_user);
    END IF;

    -- Retrofit: objects a superuser-run `migrate` already created. Empty on a
    -- fresh volume. Skips extension members, and sequences owned by a table
    -- column (ALTER TABLE ... OWNER moves those with their table).
    FOR obj IN
        SELECT c.oid::regclass AS name,
               CASE c.relkind
                   WHEN 'v' THEN 'VIEW'
                   WHEN 'm' THEN 'MATERIALIZED VIEW'
                   WHEN 'S' THEN 'SEQUENCE'
                   ELSE 'TABLE'
               END AS kind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
          AND c.relowner <> app_oid
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                AND (d.deptype = 'e' OR (c.relkind = 'S' AND d.deptype IN ('a', 'i')))
          )
    LOOP
        EXECUTE format('ALTER %s %s OWNER TO %I', obj.kind, obj.name, app_user);
    END LOOP;

    -- e.g. reject_mutation(), the append-only trigger function from
    -- apps.tenancy.db.make_append_only.
    FOR obj IN
        SELECT p.oid::regprocedure AS name
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.prokind IN ('f', 'p')
          AND p.proowner <> app_oid
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e'
          )
    LOOP
        EXECUTE format('ALTER ROUTINE %s OWNER TO %I', obj.name, app_user);
    END LOOP;

    RAISE NOTICE 'App role "%" (LOGIN CREATEDB, no SUPERUSER/BYPASSRLS) now owns database "%".',
        app_user, current_database();
END
$$;

COMMIT;
