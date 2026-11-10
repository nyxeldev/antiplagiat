import type { NextRequest } from "next/server";

const MAX_UPLOAD = 30 * 1024 * 1024 + 64 * 1024;
const MAX_CORPUS_UPLOAD = 10 * 1024 * 1024 + 64 * 1024;
function error(message: string, status: number) {
  return Response.json({ error: { message } }, { status, headers: { "Cache-Control": "no-store" } });
}

export async function proxy(request: NextRequest, path: string) {
  const mutation = !["GET", "HEAD"].includes(request.method);
  const origin = process.env.ANTIPLAGIAT_PUBLIC_ORIGIN ?? "http://127.0.0.1:3000";
  if (request.headers.get("x-antiplagiat-local") !== "1" ||
      (mutation && request.headers.get("origin") !== origin) ||
      (request.headers.get("origin") && request.headers.get("origin") !== origin) ||
      request.headers.get("sec-fetch-site") === "cross-site" ||
      request.headers.get("host") !== new URL(origin).host ||
      !["localhost", "127.0.0.1", "[::1]"].includes(request.nextUrl.hostname)) {
    return error("Faqat lokal sahifa orqali foydalaning.", 403);
  }
  // Corpus ingest carries one file, so it needs a file sized budget as well.
  // Teacher submissions go through the same CorpusUpload parser as a direct
  // admin add, so they need the same budget.
  const limit = path === "/compare" ? MAX_UPLOAD
    : (path === "/corpus/documents" || path === "/corpus/submissions") ? MAX_CORPUS_UPLOAD : 8192;
  const length = Number(request.headers.get("content-length") ?? "0");
  if (!Number.isFinite(length) || length < 0 || length > limit) return error("So‘rov hajmi chegaradan oshdi.", 413);
  const type = request.headers.get("content-type") ?? "";
  if (path === "/compare" && (!type.startsWith("multipart/form-data;") || !request.body)) return error("Fayllarni tanlang.", 400);
  let total = 0;
  const body = mutation && request.body ? request.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      total += chunk.byteLength;
      if (total > limit) throw new Error("body_limit");
      controller.enqueue(chunk);
    },
  })) : undefined;
  try {
    const api = new URL(process.env.ANTIPLAGIAT_API_URL ?? "http://127.0.0.1:8000");
    if (api.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(api.hostname) || api.username || api.password) return error("Backend manzili lokal HTTP manzil bo‘lishi kerak.", 503);
    const headers = new Headers({ "X-Antiplagiat-Local": "1" });
    if (type) headers.set("Content-Type", type);
    if (request.headers.get("origin")) headers.set("Origin", request.headers.get("origin")!);
    const cookie = request.cookies.get("antiplagiat_session")?.value;
    if (cookie && /^[A-Za-z0-9_-]{43}$/.test(cookie)) headers.set("Cookie", `antiplagiat_session=${cookie}`);
    const key = request.headers.get("idempotency-key");
    if (key) headers.set("Idempotency-Key", key);
    const options: RequestInit & { duplex?: "half" } = {
      method: request.method, body, ...(body ? { duplex: "half" as const } : {}), headers,
      cache: "no-store", redirect: "error", signal: AbortSignal.any([request.signal, AbortSignal.timeout(95_000)]),
    };
    const url = new URL(path, api);
    if (path === "/reports") url.search = request.nextUrl.search;
    if (path === "/corpus/documents") {
      const page = request.nextUrl.searchParams.get("page");
      const status = request.nextUrl.searchParams.get("status");
      const reviewStatus = request.nextUrl.searchParams.get("review_status");
      const parts: string[] = [];
      if (page && /^[0-9]+$/.test(page)) parts.push(`page=${page}`);
      if (status && ["active", "withdrawn", "all"].includes(status)) parts.push(`status=${status}`);
      if (reviewStatus && ["pending", "approved", "rejected"].includes(reviewStatus)) parts.push(`review_status=${reviewStatus}`);
      if (parts.length) url.search = parts.join("&");
    }
    if (path === "/corpus/submissions" && request.method === "GET") {
      const page = request.nextUrl.searchParams.get("page");
      if (page && /^[0-9]+$/.test(page)) url.search = `page=${page}`;
    }
    // The only compare options forwarded; everything else stays server decided.
    if (path === "/compare" && request.nextUrl.searchParams.get("include_corpus") === "true") {
      const normalization = request.nextUrl.searchParams.get("normalization");
      const allowed = normalization === "v3" || normalization === "v3-matching" ? normalization : null;
      url.search = `include_corpus=true${allowed ? `&normalization=${allowed}` : ""}`;
    }
    const response = await fetch(url, options);
    const outgoing = new Headers({ "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
    for (const value of response.headers.getSetCookie()) outgoing.append("Set-Cookie", value);
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    if (total > limit) return error("So‘rov hajmi chegaradan oshdi.", 413);
    return error("Backendga ulanib bo‘lmadi yoki vaqt tugadi. Natijani tarixdan tekshiring; qayta urinish bir xil identifikatorni ishlatadi.", 502);
  }
}
