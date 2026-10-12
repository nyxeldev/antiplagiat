import type { NextRequest } from "next/server";
import { proxy } from "../../../lib/proxy";

export const runtime = "nodejs";
export async function POST(request: NextRequest) { return proxy(request, "/compare"); }
