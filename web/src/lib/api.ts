const TOKEN_KEY = "ytauto_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(t: string | null) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const msg = data?.message || data?.detail || res.statusText;
    if (res.status === 401) setToken(null);
    throw new ApiError(msg, res.status, data?.error_code);
  }
  return data as T;
}

export async function authedBlobUrl(path: string): Promise<string> {
  const token = getToken();
  const res = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.statusText, res.status);
  return URL.createObjectURL(await res.blob());
}

export const api = {
  get: <T = any>(p: string) => request<T>("GET", p),
  post: <T = any>(p: string, body?: unknown) => request<T>("POST", p, body ?? {}),
  put: <T = any>(p: string, body?: unknown) => request<T>("PUT", p, body ?? {}),
  patch: <T = any>(p: string, body?: unknown) => request<T>("PATCH", p, body ?? {}),
  del: <T = any>(p: string) => request<T>("DELETE", p),
};
