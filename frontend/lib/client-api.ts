export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export async function api(path: string, options: RequestInit = {}) {
  const response = await fetch(`/api${path}`, {
    ...options, cache: "no-store", headers: { "X-Antiplagiat-Local": "1", ...options.headers },
  });
  const result = await response.json();
  if (!response.ok) throw new ApiError(`${result.error?.file ? `${result.error.file}: ` : ""}${result.error?.message ?? "So‘rov bajarilmadi."}`, response.status);
  return result;
}
