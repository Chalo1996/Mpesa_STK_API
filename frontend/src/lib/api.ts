export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "";
const OAUTH_ACCESS_TOKEN_ENV = import.meta.env?.VITE_OAUTH_ACCESS_TOKEN || "";
const OAUTH_ACCESS_TOKEN_STORAGE_KEY = "oauth_access_token";

export function getStoredOAuthAccessToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return (
      window.localStorage.getItem(OAUTH_ACCESS_TOKEN_STORAGE_KEY) || ""
    ).trim();
  } catch {
    return "";
  }
}

export function setStoredOAuthAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      OAUTH_ACCESS_TOKEN_STORAGE_KEY,
      (token || "").trim()
    );
  } catch {
    // ignore
  }
}

export function clearStoredOAuthAccessToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(OAUTH_ACCESS_TOKEN_STORAGE_KEY);
  } catch {
    // ignore
  }
}

function getCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const part of cookies) {
    const [k, ...rest] = part.trim().split("=");
    if (k === name) {
      return decodeURIComponent(rest.join("="));
    }
  }
  return "";
}

export async function apiRequest(
  path: string,
  options?: RequestInit
): Promise<{ status: number; data: unknown }> {
  const headers = new Headers(options?.headers || undefined);

  // If the caller didn't explicitly set Authorization, automatically attach a
  // stored OAuth2 access token (developer portal flow).
  // Avoid attaching it to login/csrf/token endpoints.
  const shouldAttachBearer =
    !headers.has("Authorization") &&
    !path.startsWith("/api/v1/auth/") &&
    path !== "/api/v1/oauth/token/";
  if (shouldAttachBearer) {
    const stored = getStoredOAuthAccessToken();
    const token = stored || String(OAUTH_ACCESS_TOKEN_ENV || "").trim();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const method = (options?.method || "GET").toUpperCase();
  const isUnsafe = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
  if (isUnsafe && !headers.has("X-CSRFToken")) {
    const token = getCookie("csrftoken");
    if (token) headers.set("X-CSRFToken", token);
  }

  if (options?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  const contentType = response.headers.get("content-type") || "";
  let data: unknown = null;
  if (contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    data = await response.text().catch(() => "");
  }

  return { status: response.status, data };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  return String(value);
}

function pickMessageFromObject(obj: Record<string, unknown>): string {
  const direct = asString(obj["status_message"]).trim();
  if (direct) return direct;

  const error = asString(obj["error"]).trim();
  if (error) return error;

  const resultDesc = asString(obj["ResultDesc"]).trim();
  if (resultDesc) return resultDesc;

  const responseDesc = asString(obj["ResponseDescription"]).trim();
  if (responseDesc) return responseDesc;

  const altResponseDesc = asString(obj["responseDescription"]).trim();
  if (altResponseDesc) return altResponseDesc;

  // Common nested shapes.
  for (const nestedKey of [
    "payment_request",
    "paymentRequest",
    "request",
    "batch",
    "data",
    "result",
  ]) {
    const nested = obj[nestedKey];
    if (isRecord(nested)) {
      const msg = pickMessageFromObject(nested);
      if (msg) return msg;
    }
  }

  return "";
}

export function extractStatusMessage(data: unknown): string {
  if (isRecord(data)) return pickMessageFromObject(data);
  return asString(data).trim();
}

export async function ensureCsrfCookie(): Promise<void> {
  await apiRequest("/api/v1/auth/csrf", { method: "GET" });
}
