import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import TrialReconstruction from "./TrialReconstruction";

const stimuli = [
  { ordinal: 0, filename: "alpha.mp4" },
  { ordinal: 1, filename: "beta.mp4" },
  { ordinal: 2, filename: "gamma.mp4" },
];

describe("TrialReconstruction", () => {
  it("shows exact submitted positions and trial timing", () => {
    render(
      <TrialReconstruction
        trials={[
          {
            id: "trial-1",
            trial_index: 0,
            subset_indices: [0, 2],
            positions: {
              "0": [110.25, 205.5],
              "2": [330.75, 410.125],
            },
            duration_seconds: 42.25,
            started_at: "2026-05-14T12:00:00Z",
            completed_at: "2026-05-14T12:00:42Z",
          },
        ]}
        stimuli={stimuli}
      />
    );

    expect(screen.getByText("Trial 1")).toBeInTheDocument();
    expect(screen.getByText("42.25s")).toBeInTheDocument();
    expect(screen.getByText("alpha.mp4")).toBeInTheDocument();
    expect(screen.getByText("gamma.mp4")).toBeInTheDocument();
    expect(screen.getByText("110.25, 205.50")).toBeInTheDocument();
    expect(screen.getByText("330.75, 410.13")).toBeInTheDocument();
  });
});
