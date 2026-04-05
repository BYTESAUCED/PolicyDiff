const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");

type QueryValue = string | number | boolean | null | undefined;

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export function buildApiUrl(
  path: string,
  query?: Record<string, QueryValue>
): string {
  const search = new URLSearchParams();

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        search.set(key, String(value));
      }
    }
  }

  const queryString = search.toString();
  const relativeUrl = `${path}${queryString ? `?${queryString}` : ""}`;
  return API_BASE_URL ? `${API_BASE_URL}${relativeUrl}` : relativeUrl;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  query?: Record<string, QueryValue>
): Promise<T> {
  const headers = new Headers(init?.headers);
  const body = init?.body;

  if (body && !(body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildApiUrl(path, query), {
    ...init,
    headers,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "object" &&
      payload !== null &&
      "message" in payload &&
      typeof payload.message === "string"
        ? payload.message
        : typeof payload === "object" &&
          payload !== null &&
          "error" in payload &&
          typeof payload.error === "string"
          ? payload.error
          : `Request failed with status ${response.status}`;

    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}
