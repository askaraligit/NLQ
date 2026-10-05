import { NLQApiError } from "@/lib/api/nlq";
import { publicEnv } from "@/lib/env";

export type SessionUser = { id: string; email: string; displayName: string };
export type LoginResult = { accessToken: string; expiresIn: number; user: SessionUser };
export type WorkspaceSettings = { preferredPageSize: 10 | 25 | 50 | 100; compactTables: boolean };

async function request(path: string, init: RequestInit = {}) {
  const response = await fetch(`${publicEnv.apiUrl}${path}`, init);
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    const message = typeof data === "object" && data !== null && "detail" in data
      ? typeof data.detail === "string" ? data.detail : "The request could not be completed."
      : "The request could not be completed.";
    throw new NLQApiError(`HTTP_${response.status}`, message);
  }
  return response.status === 204 ? null : response.json() as Promise<unknown>;
}

export async function login(email: string, password: string): Promise<LoginResult> {
  return request("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) }) as Promise<LoginResult>;
}

export async function fetchSettings(token: string): Promise<WorkspaceSettings> {
  return request("/auth/settings", { headers: { Authorization: `Bearer ${token}` } }) as Promise<WorkspaceSettings>;
}

export async function updateSettings(token: string, settings: WorkspaceSettings): Promise<WorkspaceSettings> {
  return request("/auth/settings", { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(settings) }) as Promise<WorkspaceSettings>;
}
