import { deriveTrialAdvanceState } from "./experimentHelpers";

describe("deriveTrialAdvanceState", () => {
  it("starts a non-final trial immediately and seeds the session clock", () => {
    const now = 12345;
    const state = deriveTrialAdvanceState(
      {
        trial_index: 2,
        subset_indices: [1, 3, 5],
        is_final: false,
      },
      now,
      null
    );

    expect(state).toEqual({
      trialIndex: 2,
      isFinal: false,
      subsetIndices: [1, 3, 5],
      trialStartedAt: now,
      sessionStartAt: now,
    });
  });

  it("preserves the existing session start when advancing", () => {
    const state = deriveTrialAdvanceState(
      {
        trial_index: 4,
        subset_indices: [0, 2],
        is_final: false,
      },
      99999,
      111
    );

    expect(state.sessionStartAt).toBe(111);
    expect(state.trialStartedAt).toBe(99999);
  });

  it("marks final state without creating a new trial start time", () => {
    const state = deriveTrialAdvanceState(
      {
        trial_index: 6,
        subset_indices: [0, 1],
        is_final: true,
      },
      777,
      222
    );

    expect(state).toEqual({
      trialIndex: 6,
      isFinal: true,
      subsetIndices: [],
      trialStartedAt: null,
      sessionStartAt: 222,
    });
  });
});
