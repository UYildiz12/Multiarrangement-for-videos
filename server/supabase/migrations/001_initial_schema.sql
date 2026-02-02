-- Multiarrangement Web Migration
-- Initial Schema Migration

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (extends Supabase auth.users)
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'researcher' CHECK (role IN ('admin', 'researcher')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Studies table
CREATE TABLE public.studies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    paradigm TEXT NOT NULL CHECK (paradigm IN ('setcover', 'adaptive')),
    config JSONB NOT NULL DEFAULT '{}',
    language TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'tr')),
    instructions TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Stimuli table
CREATE TABLE public.stimuli (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    study_id UUID NOT NULL REFERENCES public.studies(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('video', 'audio', 'image')),
    storage_path TEXT NOT NULL,
    duration_seconds REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (study_id, ordinal)
);

-- Sessions table
CREATE TABLE public.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    study_id UUID NOT NULL REFERENCES public.studies(id) ON DELETE CASCADE,
    participant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    batches JSONB,
    current_trial_index INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Trials table
CREATE TABLE public.trials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
    trial_index INTEGER NOT NULL,
    subset_indices INTEGER[] NOT NULL,
    duration_seconds REAL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE (session_id, trial_index)
);

-- Trial positions table
CREATE TABLE public.trial_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trial_id UUID NOT NULL REFERENCES public.trials(id) ON DELETE CASCADE,
    stimulus_id UUID NOT NULL REFERENCES public.stimuli(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    UNIQUE (trial_id, stimulus_id)
);

-- Indexes for common queries
CREATE INDEX idx_studies_owner ON public.studies(owner_id);
CREATE INDEX idx_stimuli_study ON public.stimuli(study_id);
CREATE INDEX idx_sessions_study ON public.sessions(study_id);
CREATE INDEX idx_trials_session ON public.trials(session_id);
CREATE INDEX idx_trial_positions_trial ON public.trial_positions(trial_id);

-- Row Level Security policies
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.studies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stimuli ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trial_positions ENABLE ROW LEVEL SECURITY;

-- Users can read their own data
CREATE POLICY "Users can view own data" ON public.users
    FOR SELECT USING (auth.uid() = id);

-- Study owners can manage their studies
CREATE POLICY "Owners can manage studies" ON public.studies
    FOR ALL USING (auth.uid() = owner_id);

-- Stimuli follow study access
CREATE POLICY "Study access for stimuli" ON public.stimuli
    FOR ALL USING (
        EXISTS (SELECT 1 FROM public.studies WHERE studies.id = stimuli.study_id AND studies.owner_id = auth.uid())
    );

-- Sessions are public for participants but managed by owners
CREATE POLICY "Public session read" ON public.sessions
    FOR SELECT USING (true);

CREATE POLICY "Owners manage sessions" ON public.sessions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM public.studies WHERE studies.id = sessions.study_id AND studies.owner_id = auth.uid())
    );

-- Trials follow session access
CREATE POLICY "Public trial read" ON public.trials
    FOR SELECT USING (true);

CREATE POLICY "Session owners manage trials" ON public.trials
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Trial update by session" ON public.trials
    FOR UPDATE USING (true);

-- Trial positions follow trial access
CREATE POLICY "Public position read" ON public.trial_positions
    FOR SELECT USING (true);

CREATE POLICY "Position insert" ON public.trial_positions
    FOR INSERT WITH CHECK (true);
