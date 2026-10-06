import { publicEnv } from "@/lib/env";
import type { NLQQueryResponse, QueryCell, QueryRow, Visualization } from "@/types/nlq";

type ApiErrorPayload = {
  error?: {
    code?: unknown;
    message?: unknown;
  };
};

const visualizationTypes = ["table", "bar", "line", "area", "pie"] as const;

export class NLQApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "NLQApiError";
    this.code = code;
  }
}

export type ModelOptions = { provider: string; defaultModel: string; models: string[] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readCell(value: unknown): QueryCell {
  if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") {
    return value;
  }
  throw new NLQApiError("INVALID_RESPONSE", "The query service returned an invalid result value.");
}

function readRows(value: unknown): QueryRow[] {
  if (!Array.isArray(value)) {
    throw new NLQApiError("INVALID_RESPONSE", "The query service returned invalid rows.");
  }
  return value.map((row) => {
    if (!isRecord(row)) {
      throw new NLQApiError("INVALID_RESPONSE", "The query service returned an invalid row.");
    }
    return Object.fromEntries(Object.entries(row).map(([key, cell]) => [key, readCell(cell)]));
  });
}

function readVisualization(value: unknown): Visualization {
  if (!isRecord(value) || typeof value.type !== "string") {
    throw new NLQApiError("INVALID_RESPONSE", "The query service returned invalid visualization data.");
  }
  if (!isVisualizationType(value.type)) {
    throw new NLQApiError("INVALID_RESPONSE", "The query service returned an unknown visualization type.");
  }
  const axis = (name: "xAxis" | "yAxis") => {
    const valueAtAxis = value[name];
    return typeof valueAtAxis === "string" || valueAtAxis === null ? valueAtAxis : null;
  };
  return { type: value.type, xAxis: axis("xAxis"), yAxis: axis("yAxis") };
}

function isVisualizationType(value: string): value is Visualization["type"] {
  return visualizationTypes.some((type) => type === value);
}

function readRequiredString(payload: Record<string, unknown>, field: string): string {
  const value = payload[field];
  if (typeof value !== "string") {
    throw new NLQApiError("INVALID_RESPONSE", "The query service returned an incomplete response.");
  }
  return value;
}

function readQueryResponse(payload: unknown): NLQQueryResponse {
  if (!isRecord(payload) || !Array.isArray(payload.columns)) {
    throw new NLQApiError("INVALID_RESPONSE", "The query service returned an invalid response.");
  }
  if (typeof payload.executionTimeMs !== "number") {
    throw new NLQApiError("INVALID_RESPONSE", "The query service returned invalid timing data.");
  }
  const columns = payload.columns.map((column) => {
    if (!isRecord(column) || typeof column.name !== "string") {
      throw new NLQApiError("INVALID_RESPONSE", "The query service returned invalid columns.");
    }
    return { name: column.name };
  });
  return {
    queryId: readRequiredString(payload, "queryId"),
    conversationId: readRequiredString(payload, "conversationId"),
    question: readRequiredString(payload, "question"),
    sql: readRequiredString(payload, "sql"),
    queryLanguage: payload.queryLanguage === "mongodb" ? "mongodb" : "sql",
    columns,
    rows: readRows(payload.rows),
    summary: readRequiredString(payload, "summary"),
    visualization: readVisualization(payload.visualization),
    executionTimeMs: payload.executionTimeMs,
  };
}

async function readError(response: Response): Promise<NLQApiError> {
  const payload: unknown = await response.json().catch(() => null);
  const error = isRecord(payload) ? (payload as ApiErrorPayload).error : undefined;
  const code = typeof error?.code === "string" ? error.code : `HTTP_${response.status}`;
  const message =
    typeof error?.message === "string"
      ? error.message
      : "We could not complete that query. Please try again.";
  return new NLQApiError(code, message);
}

export async function submitQuery(
  question: string,
  token: string,
  conversationId?: string,
  signal?: AbortSignal,
  model?: string,
): Promise<NLQQueryResponse> {
  const response = await fetch(`${publicEnv.apiUrl}/nlq/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question, ...(conversationId ? { conversationId } : {}), ...(model ? { model } : {}) }),
    signal,
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return readQueryResponse(await response.json());
}

export async function getModelOptions(token: string): Promise<ModelOptions> {
  const response = await fetch(`${publicEnv.apiUrl}/nlq/models`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw await readError(response);
  const payload: unknown = await response.json();
  if (!isRecord(payload) || typeof payload.provider !== "string" || typeof payload.defaultModel !== "string" || !Array.isArray(payload.models) || !payload.models.every((value) => typeof value === "string")) {
    throw new NLQApiError("INVALID_RESPONSE", "The model service returned an invalid response.");
  }
  return { provider: payload.provider, defaultModel: payload.defaultModel, models: payload.models };
}
