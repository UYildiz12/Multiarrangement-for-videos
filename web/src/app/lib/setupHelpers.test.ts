import {
  AUDIO_DURATION_FALLBACK,
  IMAGE_DURATION_FALLBACK,
  VIDEO_DURATION_FALLBACK,
  buildInstructions,
  buildStudyScopedPath,
  coalesceDuration,
  dataUrlToBlob,
  detectUploadedMediaType,
  getFileExtension,
  hasUnhostableCustomMedia,
  parseCustomInstructions,
  serializeVideosForSession,
} from "./setupHelpers";

describe("setupHelpers", () => {
  it("parses custom instruction blocks", () => {
    expect(parseCustomInstructions(" line one \n\nline two\n")).toEqual(["line one", "line two"]);
  });

  it("builds default and custom instructions", () => {
    expect(buildInstructions({
      paradigm: "setcover",
      instructionsMode: "en",
      customInstructions: "",
    })).toHaveLength(3);

    expect(buildInstructions({
      paradigm: "pairwise",
      instructionsMode: "custom",
      customInstructions: "First\nSecond",
    })).toEqual(["First", "Second"]);

    expect(buildInstructions({
      paradigm: "adaptive",
      instructionsMode: "off",
      customInstructions: "",
    })).toBeNull();
  });

  it("detects upload type from MIME and file extension", () => {
    expect(detectUploadedMediaType(new File(["x"], "clip.avi", { type: "" }))).toBe("video");
    expect(detectUploadedMediaType(new File(["x"], "sound.wav", { type: "" }))).toBe("audio");
    expect(detectUploadedMediaType(new File(["x"], "image.jpeg", { type: "" }))).toBe("image");
    expect(detectUploadedMediaType(new File(["x"], "frame.png", { type: "image/png" }))).toBe("image");
    expect(detectUploadedMediaType(new File(["x"], "notes.txt", { type: "text/plain" }))).toBeNull();
  });

  it("coalesces missing durations by media type", () => {
    expect(coalesceDuration(undefined, "image")).toBe(IMAGE_DURATION_FALLBACK);
    expect(coalesceDuration(null, "audio")).toBe(AUDIO_DURATION_FALLBACK);
    expect(coalesceDuration(undefined, "video")).toBe(VIDEO_DURATION_FALLBACK);
    expect(coalesceDuration(7.5, "video")).toBe(7.5);
  });

  it("extracts file extensions and safe storage paths", () => {
    expect(getFileExtension("Example.JPG")).toBe("jpg");

    const originalCrypto = global.crypto;
    Object.defineProperty(global, "crypto", {
      value: { randomUUID: () => "abcd-1234" },
      configurable: true,
    });

    expect(buildStudyScopedPath("owner", "study", "media", 5, "clip name", "mp4"))
      .toBe("owners/owner/studies/study/media/005_clip_name_abcd1234.mp4");

    Object.defineProperty(global, "crypto", {
      value: originalCrypto,
      configurable: true,
    });
  });

  it("detects unhostable local media", () => {
    expect(hasUnhostableCustomMedia([
      {
        name: "a",
        url: "blob:abc",
        selected: true,
        mediaType: "video",
      },
    ])).toBe(true);

    expect(hasUnhostableCustomMedia([
      {
        name: "a",
        url: "blob:abc",
        selected: true,
        mediaType: "video",
        sourceFile: new File(["x"], "clip.mp4", { type: "video/mp4" }),
      },
    ])).toBe(false);
  });

  it("converts data URLs to blobs and strips local-only fields", async () => {
    const blob = dataUrlToBlob("data:text/plain;base64,aGVsbG8=");
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe("text/plain");
    expect(blob.size).toBeGreaterThan(0);

    const serialized = serializeVideosForSession([
      {
        name: "clip",
        url: "https://example.com/clip.mp4",
        thumbnail: "https://example.com/thumb.jpg",
        selected: true,
        mediaType: "video",
        durationSeconds: 4,
        sourceFile: new File(["x"], "clip.mp4", { type: "video/mp4" }),
        thumbnailDataUrl: "data:image/jpeg;base64,AA==",
        mediaStoragePath: "owners/o/studies/s/media/clip.mp4",
        thumbnailStoragePath: "owners/o/studies/s/thumbs/clip.jpg",
      },
    ]);

    expect(serialized).toEqual([
      {
        name: "clip",
        url: "https://example.com/clip.mp4",
        thumbnail: "https://example.com/thumb.jpg",
        selected: true,
        mediaType: "video",
        durationSeconds: 4,
        mediaStoragePath: "owners/o/studies/s/media/clip.mp4",
        thumbnailStoragePath: "owners/o/studies/s/thumbs/clip.jpg",
      },
    ]);
  });
});
