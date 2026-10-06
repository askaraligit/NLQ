import { NLQApiError } from "@/lib/api/nlq";
import { publicEnv } from "@/lib/env";

export type SourceType = "postgresql" | "mongodb";

export type DataConnection = {
  id: string;
  name: string;
  sourceType: SourceType;
  schemaName: string;
  databaseName: string | null;
  isActive: boolean;
  createdAt: string;
};

async function request(path: string, token: string, init: RequestInit = {}) {
  const response = await fetch(`${publicEnv.apiUrl}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...init.headers },
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const message = typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string"
      ? payload.detail : "The connection request could not be completed.";
    throw new NLQApiError(`HTTP_${response.status}`, message);
  }
  return response.status === 204 ? null : response.json() as Promise<unknown>;
}

export const getConnections = (token: string) => request("/connections", token) as Promise<DataConnection[]>;
export const createConnection = (token: string, body: { name: string; sourceType: SourceType; connectionUrl: string; schemaName: string; databaseName?: string }) => request("/connections", token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) as Promise<DataConnection>;
export const activateConnection = (token: string, id: string) => request(`/connections/${id}/activate`, token, { method: "POST" }) as Promise<DataConnection>;
export const deleteConnection = (token: string, id: string) => request(`/connections/${id}`, token, { method: "DELETE" }) as Promise<null>;
