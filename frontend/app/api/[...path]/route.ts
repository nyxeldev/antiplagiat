import type { NextRequest } from "next/server";
import { proxy } from "../../../lib/proxy";

export const runtime = "nodejs";
async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = `/${path.join("/")}`;
  const allowed = (request.method === "GET" && (target === "/auth/me" || target === "/reports" || /^\/reports\/[0-9a-f-]{36}$/i.test(target))) ||
    (request.method === "POST" && ["/auth/login", "/auth/logout"].includes(target)) ||
    (request.method === "DELETE" && /^\/reports\/[0-9a-f-]{36}$/i.test(target));
  if (!allowed) return Response.json({ error: { message: "Topilmadi." } }, { status: 404, headers: { "Cache-Control": "no-store" } });
  return proxy(request, target);
}
export const GET = handle;
export const POST = handle;
export const DELETE = handle;
