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

  it("plots submitted coordinates in the original arena frame when arena_size is available", () => {
    render(
      <TrialReconstruction
        trials={[
          {
            id: "trial-1",
            trial_index: 0,
            subset_indices: [0, 1, 2],
            arena_size: 600,
            positions: {
              "0": [300, 300],
              "1": [580, 300],
              "2": [300, 20],
            },
            duration_seconds: 12,
            started_at: "2026-05-14T12:00:00Z",
            completed_at: "2026-05-14T12:00:12Z",
          },
        ]}
        stimuli={stimuli}
      />
    );

    const centerPoint = screen.getByTestId("trial-0-point-0");
    const rightPoint = screen.getByTestId("trial-0-point-1");
    const topPoint = screen.getByTestId("trial-0-point-2");
    const svg = screen.getByRole("img", { name: "Trial 1 submitted arrangement" });

    expect(svg).toHaveAttribute("data-arena-size", "600");
    expect(centerPoint).toHaveAttribute("cx", "110.00");
    expect(centerPoint).toHaveAttribute("cy", "90.00");
    expect(rightPoint).toHaveAttribute("cx", "184.00");
    expect(rightPoint).toHaveAttribute("cy", "90.00");
    expect(topPoint).toHaveAttribute("cx", "110.00");
    expect(topPoint).toHaveAttribute("cy", "16.00");
  });

  it("infers the source arena for older trials instead of min-max stretching points", () => {
    render(
      <TrialReconstruction
        trials={[
          {
            id: "trial-1",
            trial_index: 0,
            subset_indices: [0, 1, 2],
            positions: {
              "0": [361, 60],
              "1": [555.54, 379.5],
              "2": [128.46, 202.5],
            },
            duration_seconds: 12,
            started_at: "2026-05-14T12:00:00Z",
            completed_at: "2026-05-14T12:00:12Z",
          },
        ]}
        stimuli={stimuli}
      />
    );

    const svg = screen.getByRole("img", { name: "Trial 1 submitted arrangement" });
    const upperPoint = screen.getByTestId("trial-0-point-0");

    expect(svg).toHaveAttribute("data-arena-size", "600");
    expect(upperPoint).toHaveAttribute("cx", "126.12");
    expect(upperPoint).toHaveAttribute("cy", "26.57");
  });
});
