export interface NextTrialResponse {
  trial_index: number;
  subset_indices: number[];
  is_final: boolean;
}

export interface TrialAdvanceState {
  trialIndex: number;
  isFinal: boolean;
  subsetIndices: number[];
  trialStartedAt: number | null;
  sessionStartAt: number | null;
}

export function deriveTrialAdvanceState(
  next: NextTrialResponse,
  now: number,
  currentSessionStartAt: number | null
): TrialAdvanceState {
  if (next.is_final) {
    return {
      trialIndex: next.trial_index,
      isFinal: true,
      subsetIndices: [],
      trialStartedAt: null,
      sessionStartAt: currentSessionStartAt,
    };
  }

  return {
    trialIndex: next.trial_index,
    isFinal: false,
    subsetIndices: next.subset_indices,
    trialStartedAt: now,
    sessionStartAt: currentSessionStartAt ?? now,
  };
}
