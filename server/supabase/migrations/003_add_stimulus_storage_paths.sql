alter table public.stimuli
add column if not exists media_storage_path text;

alter table public.stimuli
add column if not exists thumbnail_storage_path text;
