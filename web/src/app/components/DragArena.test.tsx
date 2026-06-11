import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import DragArena, {
  computeSeatLayout,
  getTokenRadiusForStimulusCount,
  type TraceSample,
} from "./DragArena";

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

  it("keeps dense first-trial tokens comfortably sized via multi-ring seating", () => {
    const radius = getTokenRadiusForStimulusCount(58, 750);
    expect(radius).toBeGreaterThanOrEqual(24);
  });

  it("seats large batches without overlap", () => {
    const layout = computeSeatLayout(58, 750);
    expect(layout.seats).toHaveLength(58);
    const minGap = 2 * layout.radius - 1; // allow subpixel rounding
    for (let i = 0; i < layout.seats.length; i += 1) {
      for (let j = i + 1; j < layout.seats.length; j += 1) {
        const dx = layout.seats[i].x - layout.seats[j].x;
        const dy = layout.seats[i].y - layout.seats[j].y;
        expect(Math.hypot(dx, dy)).toBeGreaterThanOrEqual(minGap);
      }
    }
    // Every seat sits outside the arena circle.
    const center = 750 / 2;
    const arenaRadius = 750 / 2 - 20;
    for (const seat of layout.seats) {
      expect(Math.hypot(seat.x - center, seat.y - center)).toBeGreaterThan(arenaRadius);
    }
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

  it("keeps the dense all-video arena free of status badges", () => {
    render(
      <DragArena
        stimuli={makeStimuli(58, "video")}
        playedItems={new Set(["stim-0", "stim-1"])}
        size={750}
        trialIndex={0}
      />
    );

    expect(screen.queryByText("Played 2/58")).not.toBeInTheDocument();
    expect(screen.queryByText("Move all items into the circle")).not.toBeInTheDocument();
  });

  it("places the Done button slightly left of the arena edge", () => {
    render(<DragArena stimuli={makeStimuli(4)} size={600} trialIndex={0} />);

    expect(screen.getByRole("button", { name: "Done" })).toHaveStyle({ left: "-12px" });
  });

  it("renders zoom controls", () => {
    render(<DragArena stimuli={makeStimuli(4)} size={600} trialIndex={0} />);
    expect(screen.getByRole("button", { name: "Zoom in" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zoom out" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset view" })).toBeInTheDocument();
  });

  it("emits pickup, move, and drop trace samples in logical coordinates", () => {
    let nowMs = 1000;
    vi.spyOn(performance, "now").mockImplementation(() => nowMs);
    const samples: TraceSample[] = [];

    render(
      <DragArena
        stimuli={makeStimuli(1)}
        size={600}
        trialIndex={0}
        onTraceSample={(sample) => samples.push(sample)}
      />
    );

    const token = screen.getByLabelText("Play stimulus Stimulus 1");
    fireEvent.pointerDown(token, { pointerId: 1, clientX: 100, clientY: 100, button: 0 });
    expect(samples).toHaveLength(1);
    expect(samples[0].phase).toBe(0);
    const startX = samples[0].x;

    nowMs += 100;
    fireEvent.pointerMove(window, { pointerId: 1, clientX: 130, clientY: 100 });
    expect(samples).toHaveLength(2);
    expect(samples[1].phase).toBe(1);
    expect(samples[1].x).toBeCloseTo(startX + 30, 5);

    // Throttled: too soon AND too close emits nothing.
    nowMs += 10;
    fireEvent.pointerMove(window, { pointerId: 1, clientX: 130.5, clientY: 100 });
    expect(samples).toHaveLength(2);

    nowMs += 100;
    fireEvent.pointerUp(window, { pointerId: 1, clientX: 130.5, clientY: 100 });
    expect(samples).toHaveLength(3);
    expect(samples[2].phase).toBe(2);

    vi.restoreAllMocks();
  });

  it("clips the world behind a fixed camera viewport", () => {
    render(<DragArena stimuli={makeStimuli(4)} size={600} trialIndex={0} />);
    const viewport = screen.getByTestId("arena-viewport");
    expect(viewport).toHaveStyle({ overflow: "hidden" });
    // The transformed world lives inside the clipping window.
    expect(viewport.contains(screen.getByTestId("arena-stage"))).toBe(true);
  });

  it("does not pan the arena at default zoom", () => {
    render(<DragArena stimuli={makeStimuli(4)} size={600} trialIndex={0} />);
    const stage = screen.getByTestId("arena-stage");
    expect(stage).toHaveStyle({ transform: "translate(0px, 0px) scale(1)" });

    fireEvent.pointerDown(stage, { pointerId: 3, clientX: 50, clientY: 50, button: 0 });
    fireEvent.pointerMove(window, { pointerId: 3, clientX: 250, clientY: 250 });
    fireEvent.pointerUp(window, { pointerId: 3 });

    expect(stage).toHaveStyle({ transform: "translate(0px, 0px) scale(1)" });
  });

  it("pans only while zoomed in, clamped so the arena stays in view", () => {
    render(<DragArena stimuli={makeStimuli(4)} size={600} trialIndex={0} />);
    const stage = screen.getByTestId("arena-stage");

    fireEvent.click(screen.getByRole("button", { name: "Zoom in" })); // 1.2x

    fireEvent.pointerDown(stage, { pointerId: 4, clientX: 0, clientY: 0, button: 0 });
    fireEvent.pointerMove(window, { pointerId: 4, clientX: 99999, clientY: 99999 });
    fireEvent.pointerUp(window, { pointerId: 4 });

    const transform = stage.style.transform;
    const match = transform.match(/translate\((-?[\d.]+)px, (-?[\d.]+)px\)/);
    expect(match).not.toBeNull();
    const panX = Number(match![1]);
    // Clamped to containerSize * (zoom - 1) / 2, far less than the drag distance.
    expect(panX).toBeGreaterThan(0);
    expect(panX).toBeLessThan(200);

    // Zooming back out recenters the arena.
    fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));
    expect(stage).toHaveStyle({ transform: "translate(0px, 0px) scale(1)" });
  });

  it("keeps logical coordinates invariant under zoom", () => {
    let nowMs = 1000;
    vi.spyOn(performance, "now").mockImplementation(() => nowMs);
    const samples: TraceSample[] = [];

    render(
      <DragArena
        stimuli={makeStimuli(1)}
        size={600}
        trialIndex={0}
        onTraceSample={(sample) => samples.push(sample)}
      />
    );

    // Zoom to 144% (two clicks of x1.2).
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));

    const token = screen.getByLabelText("Play stimulus Stimulus 1");
    fireEvent.pointerDown(token, { pointerId: 7, clientX: 144, clientY: 0, button: 0 });
    const startX = samples[samples.length - 1].x;

    nowMs += 100;
    // 144 client px at 1.44 zoom = 100 logical px.
    fireEvent.pointerMove(window, { pointerId: 7, clientX: 288, clientY: 0 });
    const moved = samples[samples.length - 1];
    expect(moved.phase).toBe(1);
    expect(moved.x).toBeCloseTo(startX + 100, 3);

    vi.restoreAllMocks();
  });
});
