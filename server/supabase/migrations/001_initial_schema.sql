-- Multiarrangement hosted schema
-- Durable metadata/state for studies, stimuli, sessions, trials, and regular invites.

CREATE TABLE IF NOT EXISTS public.studies (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    paradigm TEXT NOT NULL CHECK (paradigm IN ('setcover', 'adaptive', 'pairwise')),
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    language TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'tr')),
    instructions_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.stimuli (
    id UUID PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES public.studies(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('video', 'audio', 'image')),
    media_url TEXT,
    thumbnail_url TEXT,
    duration_seconds DOUBLE PRECISION,
    UNIQUE (study_id, ordinal)
);

CREATE TABLE IF NOT EXISTS public.sessions (
    id UUID PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES public.studies(id) ON DELETE CASCADE,
    participant_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    current_trial_index INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    state_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS public.trials (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
    trial_index INTEGER NOT NULL,
    subset_indices_json JSONB NOT NULL,
    positions_json JSONB,
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 7),
    duration_seconds DOUBLE PRECISION NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE (session_id, trial_index)
);

CREATE TABLE IF NOT EXISTS public.invites (
    token TEXT PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES public.studies(id) ON DELETE CASCADE,
    participant_id TEXT,
    used_session_id UUID REFERENCES public.sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_studies_owner_id ON public.studies(owner_id);
CREATE INDEX IF NOT EXISTS idx_stimuli_study_id ON public.stimuli(study_id);
CREATE INDEX IF NOT EXISTS idx_sessions_study_id ON public.sessions(study_id);
CREATE INDEX IF NOT EXISTS idx_sessions_study_participant ON public.sessions(study_id, participant_id);
CREATE INDEX IF NOT EXISTS idx_trials_session_id ON public.trials(session_id);
CREATE INDEX IF NOT EXISTS idx_invites_study_id ON public.invites(study_id);
