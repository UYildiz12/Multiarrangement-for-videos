-- Lock down tables that are managed through the FastAPI backend.
--
-- These tables live in the public schema, which Supabase exposes through
-- PostgREST and GraphQL when anon/authenticated roles have privileges.
-- The web app should not query these tables directly with the anon key;
-- FastAPI is the authorization boundary and uses a server-side database
-- connection. Enabling RLS and revoking direct API role grants clears the
-- Supabase Security Advisor warnings without adding permissive policies.

begin;

alter table public.studies enable row level security;
alter table public.stimuli enable row level security;
alter table public.sessions enable row level security;
alter table public.trials enable row level security;
alter table public.invites enable row level security;
alter table public.chains enable row level security;
alter table public.chain_studies enable row level security;
alter table public.chain_sessions enable row level security;
alter table public.chain_invites enable row level security;

revoke all privileges on table
    public.studies,
    public.stimuli,
    public.sessions,
    public.trials,
    public.invites,
    public.chains,
    public.chain_studies,
    public.chain_sessions,
    public.chain_invites
from anon, authenticated;

alter default privileges in schema public
revoke all privileges on tables from anon, authenticated;

commit;
