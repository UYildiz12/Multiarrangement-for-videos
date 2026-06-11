import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import PairwiseArena from "./PairwiseArena";

const imageStimulus = {
  id: "a",
  ordinal: 0,
  label: "Stimulus A",
  mediaUrl: "https://example.com/a.png",
  thumbnail: "https://example.com/a.png",
  mediaType: "image" as const,
};

describe("PairwiseArena", () => {
  it("submits ratings immediately for image pairs", () => {
    const onSubmit = vi.fn();
    const onMediaPlay = vi.fn();

    render(
      <PairwiseArena
        stimulusA={imageStimulus}
        stimulusB={{ ...imageStimulus, id: "b", ordinal: 1, label: "Stimulus B" }}
        onSubmit={onSubmit}
        onMediaPlay={onMediaPlay}
        trialIndex={0}
        totalTrials={3}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "5" }));
    fireEvent.click(screen.getByRole("button", { name: /Submit Rating/i }));

    expect(onSubmit).toHaveBeenCalledWith(5);
    expect(onMediaPlay).not.toHaveBeenCalled();
  });

  it("requires both non-image items to be played before submission", () => {
    const onSubmit = vi.fn();
    const onMediaPlay = vi.fn();

    render(
      <PairwiseArena
        stimulusA={{ ...imageStimulus, mediaType: "video", thumbnail: undefined, mediaUrl: "https://example.com/a.mp4" }}
        stimulusB={{ ...imageStimulus, id: "b", ordinal: 1, label: "Stimulus B", mediaType: "audio", thumbnail: undefined, mediaUrl: "https://example.com/b.mp3" }}
        onSubmit={onSubmit}
        onMediaPlay={onMediaPlay}
        trialIndex={1}
        totalTrials={3}
      />
    );

    const submit = screen.getByRole("button", { name: /Watch both & rate to continue/i });
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    expect(submit).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /Play A/i }));
    fireEvent.click(screen.getByRole("button", { name: /Play B/i }));

    expect(onMediaPlay).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("button", { name: /Submit Rating/i })).toBeEnabled();
  });
});

describe("PairwiseArena per-trial reset", () => {
  it("does not require re-viewing image stimuli on subsequent trials", () => {
    const makeImage = (id: string, ordinal: number) => ({
      id,
      ordinal,
      label: id,
      mediaUrl: `https://example.com/${id}.png`,
      thumbnail: `https://example.com/${id}.png`,
      mediaType: "image" as const,
    });
    const onSubmit = vi.fn();

    const { rerender } = render(
      <PairwiseArena
        stimulusA={makeImage("img-a", 0)}
        stimulusB={makeImage("img-b", 1)}
        onSubmit={onSubmit}
        onMediaPlay={() => {}}
        trialIndex={0}
        totalTrials={3}
      />
    );

    // Trial 1: images need no playing; rate and submit.
    fireEvent.click(screen.getByText("4"));
    const submitButton = screen.getByRole("button", { name: /Submit/i });
    expect(submitButton).toBeEnabled();
    fireEvent.click(submitButton);
    expect(onSubmit).toHaveBeenCalledWith(4);

    // Trial 2 with a fresh image pair: must be submittable after rating alone.
    rerender(
      <PairwiseArena
        stimulusA={makeImage("img-c", 2)}
        stimulusB={makeImage("img-d", 3)}
        onSubmit={onSubmit}
        onMediaPlay={() => {}}
        trialIndex={1}
        totalTrials={3}
      />
    );
    fireEvent.click(screen.getByText("5"));
    expect(screen.getByRole("button", { name: /Submit/i })).toBeEnabled();
  });
});
