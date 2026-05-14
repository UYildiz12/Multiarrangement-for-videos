import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import DragArena, { getTokenRadiusForStimulusCount } from "./DragArena";

function makeStimuli(count: number, mediaType: "video" | "image" = "image") {
  return Array.from({ length: count }, (_, i) => ({
    id: `stim-${i}`,
    ordinal: i,
    label: `Stimulus ${i + 1}`,
    mediaUrl: `https://example.com/${i}.png`,
    thumbnail: `https://example.com/${i}.png`,
    mediaType,
  }));
}

describe("DragArena", () => {
  it("keeps ordinary batch tokens large", () => {
    expect(getTokenRadiusForStimulusCount(8, 600)).toBe(55);
    expect(getTokenRadiusForStimulusCount(14, 600)).toBe(55);
  });

  it("shrinks tokens on narrow mobile arenas", () => {
    expect(getTokenRadiusForStimulusCount(8, 280)).toBe(25);
  });

  it("shrinks dense first-trial tokens enough for large adaptive studies", () => {
    const radius = getTokenRadiusForStimulusCount(58, 750);
    expect(radius).toBeGreaterThanOrEqual(16);
    expect(radius).toBeLessThanOrEqual(24);
  });

  it("renders all dense first-trial tokens as playable controls", () => {
    render(
      <DragArena
        stimuli={makeStimuli(58)}
        size={750}
        trialIndex={0}
      />
    );

    expect(screen.getAllByLabelText(/Play stimulus Stimulus/i)).toHaveLength(58);
  });

  it("shows playback progress for dense all-video trials", () => {
    render(
      <DragArena
        stimuli={makeStimuli(58, "video")}
        playedItems={new Set(["stim-0", "stim-1"])}
        size={750}
        trialIndex={0}
      />
    );

    expect(screen.getByText("Played 2/58")).toBeInTheDocument();
    expect(screen.getByText("Move all items into the circle")).toBeInTheDocument();
  });
});
