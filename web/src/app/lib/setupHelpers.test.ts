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
  parseMediaLinks,
  serializeVideosForSession,
} from "./setupHelpers";

describe("parseMediaLinks", () => {
  it("reads one link per line with optional labels and types from extensions", () => {
    const { links, errors } = parseMediaLinks(
      "https://osf.io/x/clip%20one.MP4\n\n  https://example.org/a/sound.wav  Dog barking \nhttps://example.org/pic.png?raw=1\n"
    );
    expect(errors).toEqual([]);
    expect(links).toEqual([
      { url: "https://osf.io/x/clip%20one.MP4", name: "clip one", mediaType: "video" },
      { url: "https://example.org/a/sound.wav", name: "Dog barking", mediaType: "audio" },
      { url: "https://example.org/pic.png?raw=1", name: "pic", mediaType: "image" },
    ]);
  });

  it("uses the fallback type for links without an extension and rejects other schemes", () => {
    const { links, errors } = parseMediaLinks("https://osf.io/abc12/download\njavascript:alert(1)\nnot a link", "audio");
    expect(links).toEqual([{ url: "https://osf.io/abc12/download", name: "download", mediaType: "audio" }]);
    expect(errors).toEqual(["Line 2: links must start with https://", "Line 3: not a web address"]);
  });
});

describe("setupHelpers", () => {
  it("parses custom instruction blocks", () => {
    expect(parseCustomInstructions(" line one \n\nline two\n")).toEqual(["line one", "line two"]);
  });

  it("builds default and custom instructions", () => {
    const arrangementInstructions = buildInstructions({
      paradigm: "setcover",
      instructionsMode: "en",
      customInstructions: "",
    });
    expect(arrangementInstructions).toHaveLength(4);
    expect(arrangementInstructions?.join(" ")).toContain("token centers");

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
