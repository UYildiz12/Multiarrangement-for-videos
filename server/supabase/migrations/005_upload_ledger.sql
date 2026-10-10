-- Ledger of signed upload URLs issued by the API (one row per Storage object).
--
-- Media files go from the browser straight to Supabase Storage through signed
-- upload URLs that only the API can issue. Each issued URL is recorded here so
-- the API can enforce the per-study upload cap and the per-owner storage quota,
-- and so deleting a study also removes uploads that were never registered as
-- stimuli. The API creates the same table on startup if it is missing
-- (without the foreign key) and deletes ledger rows itself on study deletion.

begin;

create table if not exists public.uploads (
    storage_path text primary key,
    owner_id uuid not null,
    study_id uuid not null references public.studies(id) on delete cascade,
    kind text not null check (kind in ('media', 'thumbnail')),
    content_type text not null,
    size_bytes bigint not null check (size_bytes >= 0),
    created_at timestamptz not null default now()
);

create index if not exists idx_uploads_owner_id on public.uploads(owner_id);
create index if not exists idx_uploads_study_id on public.uploads(study_id);

-- Same lockdown as 004: only the API's server-side connection uses this table.
alter table public.uploads enable row level security;
revoke all privileges on table public.uploads from anon, authenticated;

commit;
