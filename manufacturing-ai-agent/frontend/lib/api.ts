export type Scope = {
  start: string;
  end: string;
  machine: string;
  product: string;
  shift: "All" | "Day" | "Night";
  source: "reviewed" | "demo";
};
export type Totals = {
  planned_rolls: number | null;
  input_rolls: number | null;
  qualified_rolls: number | null;
  actual_output_m2: number | null;
  qualified_output_m2: number | null;
  attainment: string;
  qualification: string;
  record_count: number;
  machine_count: number;
  average_cycle_minutes?: number | null;
  machine_utilization?: number | null;
  estimated_capacity?: number | null;
};
export type Machine = Totals & {
  machine_id: string;
  status: string;
  cycle_minutes: null;
  utilization: null;
  abnormalities: { reported_minutes: number | null; event_count: number };
};
export type Dashboard = {
  source: string;
  scope: Scope;
  summary: Totals;
  daily: (Totals & { production_date: string })[];
  machines: Machine[];
  abnormalities: {
    reported_minutes: number | null;
    event_count: number;
    missing_minutes_count: number;
    categories: {
      label: string;
      reported_minutes: number | null;
      fraction: number | null;
      cumulative_fraction: number | null;
    }[];
  };
  records: Record<string, string | number | null>[];
  changeovers: Record<string, string>[];
  warnings: string[];
  last_recorded_date: string | null;
};
export type Citation = {
  name: string;
  location?: string;
  quote?: string;
  chunk_id?: string;
  scope?: Record<string, unknown>;
};
export type Answer = {
  mode: string;
  summary: string;
  verified_data: Record<string, unknown>;
  calculations: Record<string, unknown>;
  potential_causes: string[];
  recommendations: string[];
  sources: Citation[];
  assumptions: string[];
  tools: string[];
};
export type Capacity = {
  available_minutes: number;
  cycle_minutes: number;
  machines: number;
  downtime_minutes: number;
  units_per_cycle: number;
  output_unit: string;
  expected_yield: number;
};
export type Health = {
  status: string;
  llm_configured: boolean;
  embedding_provider: string;
  authentication: string;
  live_machines: boolean;
};
export type Doc = {
  id: string;
  name: string;
  category: string;
  provider: string;
  chunks: number;
  locations: number;
};
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch("/api" + path, {
    method: body === undefined ? "GET" : "POST",
    cache: "no-store",
    headers:
      body === undefined
        ? {}
        : {
            "X-Local-Client": "manufacturing-web",
            ...(!form ? { "Content-Type": "application/json" } : {}),
          },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  const value = await response
    .json()
    .catch(() => ({ detail: "Service returned an invalid response." }));
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : "Invalid inputs. Check dates, units and required fields.",
    );
  return value as T;
}
export const query = (scope: Scope) =>
  new URLSearchParams(
    Object.entries(scope).filter(([, value]) => value !== ""),
  ).toString();
export const fmt = (value: unknown, unit = "") =>
  value === null || value === undefined
    ? "Not available"
    : typeof value === "number"
      ? value.toLocaleString(undefined, { maximumFractionDigits: 1 }) +
        (unit ? " " + unit : "")
      : String(value);
