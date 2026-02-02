import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const VIDEO_EXTS = new Set([".mp4", ".webm", ".mov", ".mkv", ".avi"]);
const AUDIO_EXTS = new Set([".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"]);
const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"]);

function getMediaType(ext: string): "video" | "audio" | "image" | null {
  if (VIDEO_EXTS.has(ext)) return "video";
  if (AUDIO_EXTS.has(ext)) return "audio";
  if (IMAGE_EXTS.has(ext)) return "image";
  return null;
}

export async function GET() {
  const mediaDir = path.join(process.cwd(), "public", "videos");
  const thumbDir = path.join(process.cwd(), "public", "thumbnails");
  const audioPlaceholder = fs.existsSync(path.join(process.cwd(), "public", "audio.png"))
    ? "/audio.png"
    : undefined;

  let files: string[] = [];
  try {
    if (fs.existsSync(mediaDir)) {
      files = fs.readdirSync(mediaDir);
    }
  } catch {
    files = [];
  }

  const videos = files
    .map((f) => {
      const ext = path.extname(f).toLowerCase();
      const mediaType = getMediaType(ext);
      if (!mediaType) return null;

      const base = path.parse(f).name;
      let thumbnail: string | undefined;
      if (mediaType === "video") {
        const jpg = path.join(thumbDir, `${base}.jpg`);
        const png = path.join(thumbDir, `${base}.png`);
        if (fs.existsSync(jpg)) thumbnail = `/thumbnails/${base}.jpg`;
        else if (fs.existsSync(png)) thumbnail = `/thumbnails/${base}.png`;
      } else if (mediaType === "image") {
        thumbnail = `/videos/${f}`;
      } else if (mediaType === "audio") {
        thumbnail = audioPlaceholder;
      }

      return {
        filename: f,
        label: base,
        url: `/videos/${f}`,
        mediaType,
        thumbnail,
      };
    })
    .filter(Boolean);

  return NextResponse.json({ videos });
}
