export type QueryCell = boolean | number | string | null;

export type QueryRow = Record<string, QueryCell>;

export type Visualization = {
  type: "table" | "bar" | "line" | "area" | "pie";
  xAxis: string | null;
  yAxis: string | null;
};

export type NLQQueryResponse = {
  queryId: string;
  conversationId: string;
  question: string;
  sql: string;
  columns: Array<{ name: string }>;
  rows: QueryRow[];
  summary: string;
  visualization: Visualization;
  executionTimeMs: number;
};
