import type { NextRequest } from "next/server";

export const runtime = "nodejs";
const MAX_BODY = 30 * 1024 * 1024 + 64 * 1024;

function error(message: string, status: number) {
  return Response.json({ error: { message } }, { status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: NextRequest) {
  const host = request.headers.get("host");
  const origin = request.headers.get("origin");
  if (request.headers.get("x-antiplagiat-local") !== "1" ||
      (origin && origin !== `http://${host}` && origin !== `https://${host}`)) {
    return error("Faqat lokal sahifadagi yuklash formasidan foydalaning.", 403);
  }
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(request.url).hostname)) {
    return error("Bu prototip faqat lokal foydalanish uchun.", 403);
  }
  const type = request.headers.get("content-type") ?? "";
  const length = Number(request.headers.get("content-length") ?? "0");
  if (!type.startsWith("multipart/form-data;") || !request.body) return error("Fayllarni tanlang.", 400);
  if (!Number.isFinite(length) || length > MAX_BODY) return error("Jami hajm 30 MiB dan oshmasin.", 413);
  let total = 0;
  const body = request.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      total += chunk.byteLength;
      if (total > MAX_BODY) throw new Error("body_limit");
      controller.enqueue(chunk);
    },
  }));
  try {
    const api = new URL(process.env.ANTIPLAGIAT_API_URL ?? "http://127.0.0.1:8000");
    if (api.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(api.hostname) || api.username || api.password) {
      return error("Backend manzili lokal HTTP manzil bo‘lishi kerak.", 503);
    }
    const options: RequestInit & { duplex: "half" } = {
      method: "POST", body, duplex: "half", cache: "no-store", redirect: "error",
      headers: { "Content-Type": type, "X-Antiplagiat-Local": "1" },
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(95_000)]),
    };
    const response = await fetch(new URL("/compare", api), options);
    return new Response(response.body, {
      status: response.status,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  } catch {
    if (total > MAX_BODY) return error("Jami hajm 30 MiB dan oshmasin.", 413);
    return error("Backendga ulanib bo‘lmadi yoki vaqt tugadi. Lokal backend ishlayotganini tekshiring.", 502);
  }
}
