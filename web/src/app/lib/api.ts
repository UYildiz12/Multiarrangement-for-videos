const configuredBase = (process.env.NEXT_PUBLIC_API_BASE || "").trim();
export const API_BASE = configuredBase.endsWith("/")
  ? configuredBase.slice(0, -1)
  : configuredBase;

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { headers: customHeaders, ...restOptions } = options;
  const mergedHeaders: Record<string, string> = {};
  const headersObj = customHeaders ? new Headers(customHeaders) : null;
  headersObj?.forEach((value, key) => {
    mergedHeaders[key] = value;
  });
  const hasBody = restOptions.body !== undefined && restOptions.body !== null;
  const isFormData = typeof FormData !== "undefined" && restOptions.body instanceof FormData;
  if (hasBody && !isFormData && !("Content-Type" in mergedHeaders) && !("content-type" in mergedHeaders)) {
    mergedHeaders["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...restOptions,
    headers: mergedHeaders,
  });
  if (!res.ok) {
    const text = await res.text();
    // Only expose server message for expected client errors;
    // hide raw text for 5xx to avoid leaking backend internals.
    const safeStatuses = new Set([400, 401, 403, 404, 409, 422]);
    const detail = safeStatuses.has(res.status) ? text : "Internal server error";
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  if (res.status === 204 || res.status === 205) {
    return undefined as T;
  }

  const contentLength = res.headers.get("content-length");
  if (contentLength === "0") {
    return undefined as T;
  }

  const contentType = (res.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    return res.json() as Promise<T>;
  }

  const text = await res.text();
  if (!text) {
    return undefined as T;
  }
  return text as T;
}
