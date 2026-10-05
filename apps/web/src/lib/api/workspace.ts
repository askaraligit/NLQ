import { NLQApiError } from "@/lib/api/nlq";
import { publicEnv } from "@/lib/env";
import type { NLQQueryResponse, Visualization } from "@/types/nlq";

export type HistoryItem = NLQQueryResponse & { id: string; createdAt: string };
export type SavedQuery = { id: string; queryId: string; name: string; question: string; sql: string; visualization: Visualization; createdAt: string };

async function api(path: string, token: string, init: RequestInit = {}) {
  const response = await fetch(`${publicEnv.apiUrl}${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, ...init.headers } });
  if (!response.ok) {
    throw new NLQApiError(`HTTP_${response.status}`, "The workspace request could not be completed.");
  }
  return response.status === 204 ? null : response.json() as Promise<unknown>;
}

export const getHistory = (token: string) => api("/nlq/history", token) as Promise<HistoryItem[]>;
export const getSaved = (token: string) => api("/nlq/saved", token) as Promise<SavedQuery[]>;
export const saveQuery = (token: string, queryId: string, name: string) => api("/nlq/saved", token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ queryId, name }) }) as Promise<SavedQuery>;
export const deleteSaved = (token: string, id: string) => api(`/nlq/saved/${id}`, token, { method: "DELETE" }) as Promise<null>;
