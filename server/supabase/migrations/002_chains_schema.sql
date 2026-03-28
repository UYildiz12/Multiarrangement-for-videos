-- Multiarrangement hosted chains schema
-- Durable ordering, invites, and participant progress for multi-study chains.

CREATE TABLE IF NOT EXISTS public.chains (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.chain_studies (
    id UUID PRIMARY KEY,
    chain_id UUID NOT NULL REFERENCES public.chains(id) ON DELETE CASCADE,
    study_id UUID NOT NULL REFERENCES public.studies(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    UNIQUE (chain_id, position),
    UNIQUE (chain_id, study_id)
);

CREATE TABLE IF NOT EXISTS public.chain_sessions (
    id UUID PRIMARY KEY,
    chain_id UUID NOT NULL REFERENCES public.chains(id) ON DELETE CASCADE,
    invite_token TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    current_position INTEGER NOT NULL DEFAULT 0,
    current_session_id UUID REFERENCES public.sessions(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.chain_invites (
    token TEXT PRIMARY KEY,
    chain_id UUID NOT NULL REFERENCES public.chains(id) ON DELETE CASCADE,
    participant_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    chain_session_id UUID REFERENCES public.chain_sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_chains_owner_id ON public.chains(owner_id);
CREATE INDEX IF NOT EXISTS idx_chain_studies_chain_id ON public.chain_studies(chain_id);
CREATE INDEX IF NOT EXISTS idx_chain_studies_study_id ON public.chain_studies(study_id);
CREATE INDEX IF NOT EXISTS idx_chain_sessions_chain_id ON public.chain_sessions(chain_id);
CREATE INDEX IF NOT EXISTS idx_chain_sessions_chain_participant ON public.chain_sessions(chain_id, participant_id);
CREATE INDEX IF NOT EXISTS idx_chain_invites_chain_id ON public.chain_invites(chain_id);
CREATE INDEX IF NOT EXISTS idx_chain_invites_chain_session_id ON public.chain_invites(chain_session_id);
