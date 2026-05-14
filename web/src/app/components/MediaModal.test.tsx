import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import MediaModal from "./MediaModal";

describe("MediaModal", () => {
  const originalPlay = HTMLMediaElement.prototype.play;

  beforeEach(() => {
    HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  });

  afterEach(() => {
    HTMLMediaElement.prototype.play = originalPlay;
    vi.restoreAllMocks();
  });

  it("does not render when closed", () => {
    const { container } = render(
      <MediaModal
        mediaUrl="https://example.com/a.png"
        mediaType="image"
        isOpen={false}
        onClose={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders an image stimulus and closes via button and escape", () => {
    const onClose = vi.fn();

    render(
      <MediaModal
        mediaUrl="https://example.com/a.png"
        mediaType="image"
        isOpen
        onClose={onClose}
      />
    );

    expect(screen.getByAltText("Stimulus")).toHaveAttribute("src", "https://example.com/a.png");

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /Close media/i }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("renders the dedicated audio panel", () => {
    render(
      <MediaModal
        mediaUrl="https://example.com/a.mp3"
        mediaType="audio"
        isOpen
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("Audio Stimulus")).toBeInTheDocument();
    expect(screen.getByText("Playback")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Close media/i })).toBeInTheDocument();
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled();
  });
});
