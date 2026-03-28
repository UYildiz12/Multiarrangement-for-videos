import { apiFetch } from "./api";

describe("apiFetch", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("adds JSON content type for body payloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );
    global.fetch = fetchMock as typeof fetch;

    await apiFetch("/studies", {
      method: "POST",
      body: JSON.stringify({ name: "demo" }),
    });

    const [, options] = fetchMock.mock.calls[0];
    const headers = options?.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("does not force JSON content type for FormData bodies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );
    global.fetch = fetchMock as typeof fetch;
    const form = new FormData();
    form.append("file", new Blob(["x"]), "demo.txt");

    await apiFetch("/upload", {
      method: "POST",
      body: form,
    });

    const [, options] = fetchMock.mock.calls[0];
    expect(options?.headers).toEqual({});
  });

  it("returns parsed JSON responses", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "123" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    ) as typeof fetch;

    await expect(apiFetch<{ id: string }>("/studies")).resolves.toEqual({ id: "123" });
  });

  it("returns plain text responses when not JSON", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response("ok", {
        status: 200,
        headers: { "content-type": "text/plain" },
      })
    ) as typeof fetch;

    await expect(apiFetch<string>("/health")).resolves.toBe("ok");
  });

  it("returns undefined for 204 responses", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 204,
      })
    ) as typeof fetch;

    await expect(apiFetch<void>("/empty")).resolves.toBeUndefined();
  });

  it("hides raw 5xx bodies", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response("secret traceback", {
        status: 500,
        headers: { "content-type": "text/plain" },
      })
    ) as typeof fetch;

    await expect(apiFetch("/broken")).rejects.toThrow("API error 500: Internal server error");
  });

  it("surfaces raw 4xx bodies", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response("missing", {
        status: 404,
        headers: { "content-type": "text/plain" },
      })
    ) as typeof fetch;

    await expect(apiFetch("/missing")).rejects.toThrow("API error 404: missing");
  });
});
