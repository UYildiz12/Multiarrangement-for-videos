-- Multiarrangement Web Migration
-- Chains Schema Migration

-- Experiment chains table
CREATE TABLE public.chains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Chain studies (ordered list of studies in a chain)
CREATE TABLE public.chain_studies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain_id UUID NOT NULL REFERENCES public.chains(id) ON DELETE CASCADE,
    study_id UUID NOT NULL REFERENCES public.studies(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    UNIQUE (chain_id, position),
    UNIQUE (chain_id, study_id)
);

-- Chain invites
CREATE TABLE public.chain_invites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain_id UUID NOT NULL REFERENCES public.chains(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    participant_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Chain sessions (tracks participant progress through chain)
CREATE TABLE public.chain_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain_invite_id UUID NOT NULL REFERENCES public.chain_invites(id) ON DELETE CASCADE,
    current_position INTEGER NOT NULL DEFAULT 0,
    current_session_id UUID REFERENCES public.sessions(id),
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Indexes for common queries
CREATE INDEX idx_chains_owner ON public.chains(owner_id);
CREATE INDEX idx_chain_studies_chain ON public.chain_studies(chain_id);
CREATE INDEX idx_chain_studies_study ON public.chain_studies(study_id);
CREATE INDEX idx_chain_invites_chain ON public.chain_invites(chain_id);
CREATE INDEX idx_chain_invites_token ON public.chain_invites(token);
CREATE INDEX idx_chain_sessions_invite ON public.chain_sessions(chain_invite_id);

-- Row Level Security policies
ALTER TABLE public.chains ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chain_studies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chain_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chain_sessions ENABLE ROW LEVEL SECURITY;

-- Chain owners can manage their chains
CREATE POLICY "Owners can manage chains" ON public.chains
    FOR ALL USING (auth.uid() = owner_id);

-- Chain studies follow chain access
CREATE POLICY "Chain access for chain_studies" ON public.chain_studies
    FOR ALL USING (
        EXISTS (SELECT 1 FROM public.chains WHERE chains.id = chain_studies.chain_id AND chains.owner_id = auth.uid())
    );

-- Chain invites follow chain access for management, but public for participation
CREATE POLICY "Public invite read" ON public.chain_invites
    FOR SELECT USING (true);

CREATE POLICY "Owners manage invites" ON public.chain_invites
    FOR ALL USING (
        EXISTS (SELECT 1 FROM public.chains WHERE chains.id = chain_invites.chain_id AND chains.owner_id = auth.uid())
    );

-- Chain sessions are public for participants
CREATE POLICY "Public chain_session read" ON public.chain_sessions
    FOR SELECT USING (true);

CREATE POLICY "Insert chain_session" ON public.chain_sessions
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Update chain_session" ON public.chain_sessions
    FOR UPDATE USING (true);
