export type CachedMedia = {
    blob: Blob;
    mediaType: "video" | "audio" | "image";
    thumbnail?: string;
    durationSeconds?: number;
};

type CachedMediaRecord = CachedMedia & { key: string };

const DB_NAME = "multiarrangement-media-cache";
const STORE_NAME = "media";
const DB_VERSION = 1;

function openDb(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
        if (typeof indexedDB === "undefined") {
            reject(new Error("indexedDB not available"));
            return;
        }
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: "key" });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

export async function cacheMedia(key: string, media: CachedMedia): Promise<void> {
    if (!key) return;
    try {
        const db = await openDb();
        await new Promise<void>((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, "readwrite");
            const store = tx.objectStore(STORE_NAME);
            const record: CachedMediaRecord = { key, ...media };
            store.put(record);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error);
        });
    } catch {
        // ignore cache failures
    }
}

export async function getCachedMedia(key: string): Promise<CachedMedia | null> {
    if (!key) return null;
    try {
        const db = await openDb();
        const record = await new Promise<CachedMediaRecord | undefined>((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, "readonly");
            const store = tx.objectStore(STORE_NAME);
            const req = store.get(key);
            req.onsuccess = () => resolve(req.result as CachedMediaRecord | undefined);
            req.onerror = () => reject(req.error);
        });
        if (!record) return null;
        const { blob, mediaType, thumbnail, durationSeconds } = record;
        return { blob, mediaType, thumbnail, durationSeconds };
    } catch {
        return null;
    }
}
