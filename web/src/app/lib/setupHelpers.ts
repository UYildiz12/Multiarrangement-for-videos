export type SetupParadigm = "setcover" | "adaptive" | "pairwise";
export type SetupInstructionsMode = "off" | "en" | "tr" | "custom";
export type SetupMediaType = "video" | "audio" | "image";

export interface InstructionConfigLike {
  paradigm: SetupParadigm;
  instructionsMode: SetupInstructionsMode;
  customInstructions: string;
}

export interface SetupVideoFileLike {
  name: string;
  url: string;
  thumbnail?: string;
  selected: boolean;
  mediaType: SetupMediaType;
  durationSeconds?: number;
  sourceFile?: File;
  thumbnailDataUrl?: string;
  mediaStoragePath?: string;
  thumbnailStoragePath?: string;
}

export const IMAGE_DURATION_FALLBACK = 0.5;
export const AUDIO_DURATION_FALLBACK = 3.0;
export const VIDEO_DURATION_FALLBACK = 5.0;

const DEFAULT_INSTRUCTIONS = {
  en: {
    arrangement: [
      "Double-click an item to play it.",
      "Drag each item inside the white circle.",
      "Press Done once all items are inside.",
    ],
    pairwise: [
      "Play both items, then rate their similarity.",
      "Use the full 1-7 scale whenever possible.",
      "1 = very different, 7 = very similar.",
    ],
  },
  tr: {
    arrangement: [
      "Ogeleri oynatmak icin cift tiklayin (ses/video).",
      "Her ogeyi beyaz dairenin icine surukleyin.",
      "Hepsi icerideyken Bitir'e basin.",
    ],
    pairwise: [
      "Her iki ogeyi oynatin, sonra benzerlik puani verin.",
      "Mumkun oldugunca 1-7 olceginin tamamini kullanin.",
      "1 = cok farkli, 7 = cok benzer.",
    ],
  },
} as const;

const VIDEO_UPLOAD_EXTENSIONS = new Set(["mp4", "webm", "mov", "mkv", "avi"]);
const AUDIO_UPLOAD_EXTENSIONS = new Set(["mp3", "wav", "ogg", "flac", "aac", "m4a"]);
const IMAGE_UPLOAD_EXTENSIONS = new Set(["png", "jpg", "jpeg", "bmp", "tiff", "tif", "webp", "gif"]);

export function parseCustomInstructions(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

export function buildInstructions(config: InstructionConfigLike): string[] | null {
  if (config.instructionsMode === "off") return null;
  if (config.instructionsMode === "custom") {
    const custom = parseCustomInstructions(config.customInstructions || "");
    return custom.length ? custom : null;
  }
  const lang = config.instructionsMode === "tr" ? "tr" : "en";
  const key = config.paradigm === "pairwise" ? "pairwise" : "arrangement";
  return [...DEFAULT_INSTRUCTIONS[lang][key]];
}

export function getFileExtension(name: string): string {
  const parts = name.toLowerCase().split(".");
  return parts.length > 1 ? parts[parts.length - 1] : "";
}

export function detectUploadedMediaType(file: Pick<File, "name" | "type">): SetupMediaType | null {
  const mime = (file.type || "").toLowerCase();
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  if (mime.startsWith("image/")) return "image";

  const ext = getFileExtension(file.name);
  if (VIDEO_UPLOAD_EXTENSIONS.has(ext)) return "video";
  if (AUDIO_UPLOAD_EXTENSIONS.has(ext)) return "audio";
  if (IMAGE_UPLOAD_EXTENSIONS.has(ext)) return "image";
  return null;
}

export function coalesceDuration(value: number | null | undefined, mediaType: SetupMediaType): number {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
  if (mediaType === "image") return IMAGE_DURATION_FALLBACK;
  if (mediaType === "audio") return AUDIO_DURATION_FALLBACK;
  return VIDEO_DURATION_FALLBACK;
}

export function dataUrlToBlob(dataUrl: string): Blob {
  const [meta, data] = dataUrl.split(",");
  const match = /data:(.*);base64/.exec(meta);
  const mime = match ? match[1] : "image/jpeg";
  const binary = atob(data);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mime });
}

export function safeName(name: string): string {
  return name.replace(/[^a-zA-Z0-9_-]+/g, "_");
}

export function hasUnhostableCustomMedia(videos: SetupVideoFileLike[]): boolean {
  return videos.some((video) => {
    const hasHostedPath = Boolean(video.mediaStoragePath);
    const canUploadNow = Boolean(video.sourceFile);
    const isLocalBlob = video.url.startsWith("blob:");
    return isLocalBlob && !hasHostedPath && !canUploadNow;
  });
}

export function createUploadToken(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replace(/-/g, "");
  }
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

export function buildStudyScopedPath(
  ownerId: string,
  studyId: string,
  section: "media" | "thumbs",
  index: number,
  label: string,
  ext: string
): string {
  return `owners/${ownerId}/studies/${studyId}/${section}/${String(index).padStart(3, "0")}_${safeName(label)}_${createUploadToken()}.${ext}`;
}

export function serializeVideosForSession(
  videos: SetupVideoFileLike[]
): Array<Omit<SetupVideoFileLike, "sourceFile" | "thumbnailDataUrl">> {
  return videos.map((video) => {
    const serialized = { ...video };
    delete serialized.sourceFile;
    delete serialized.thumbnailDataUrl;
    return serialized;
  });
}
