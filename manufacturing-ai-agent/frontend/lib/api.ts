export type Scope = {
  start: string;
  end: string;
  machine: string;
  product: string;
  shift: "All" | "Day" | "Night";
  source: "reviewed";
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
export type RuntimeTotals = {
  status: "estimated" | "unavailable";
  observed_shift_count: number;
  possible_shift_count: number;
  unrecorded_shift_count: number;
  invalid_event_count: number;
  no_recorded_stop_shift_count: number;
  available_minutes: number | null;
  merged_stop_minutes: number | null;
  runtime_lower_minutes: number | null;
  runtime_upper_minutes: number | null;
  utilization_lower: number | null;
  utilization_upper: number | null;
  reason: string | null;
};
export type RuntimeEstimate = RuntimeTotals & {
  source: "reviewed" | "demo";
  basis: "12h-shift-2h-flexible-break-all-events-stop-v1";
  shift_minutes: 720;
  break_minutes: 120;
  available_minutes_per_shift: 600;
  assumptions: string[];
  per_machine: (RuntimeTotals & { machine_id: string })[];
};
export type Machine = Totals & {
  machine_id: string;
  status: string;
  cycle_minutes: null;
  utilization: null;
  abnormalities: { reported_minutes: number | null; event_count: number };
  runtime_estimate: RuntimeTotals | null;
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
  runtime_estimate: RuntimeEstimate;
};
export type Citation = {
  name: string;
  location?: string;
  quote?: string;
  chunk_id?: string;
  scope?: Record<string, unknown>;
};
export type QualityGroup = {
  label: string;
  detail_count: number;
  rejected_area_m2: string;
};
export type QualitySummary = {
  scope: Scope;
  source: "reviewed";
  unit: "m2";
  status: "recorded" | "no_records" | "not_imported";
  detail_count: number;
  machine_count: number;
  rejected_area_m2: string | null;
  by_machine: QualityGroup[];
  by_reason: QualityGroup[];
  daily: QualityGroup[];
  recorded_dates: string[];
  missing_dates: string[];
  recorded_shifts: ("Day" | "Night")[];
  matched_production_group_count: number;
  unmatched_production_group_count: number;
};
export type QualityRecords = {
  scope: Scope;
  unit: "m2";
  total: number;
  offset: number;
  limit: number;
  records: Record<string, string>[];
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
        : Array.isArray(value.detail)
          ? value.detail
              .map(
                (issue: { loc?: string[]; msg?: string }) =>
                  `${issue.loc?.slice(1).join(".") || "Record"}: ${issue.msg || "Invalid value"}`,
              )
              .join("; ")
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

export type ResearchInputs = {
  planned_inputs: number | null;
  actual_inputs: number | null;
  difference: number | null;
  shortfall: number | null;
  net_shortfall: number | null;
  excess: number | null;
  record_count: number;
};
export type ResearchEventStats = {
  event_count: number;
  reported_minutes: number | null;
  valid_minutes_count: number;
  missing_minutes_count: number;
  open_count: number;
  unknown_status_count: number;
  unknown_shift_count: number;
  incomplete_time_count: number;
  mismatch_count: number;
  overlap_event_count: number;
};
export type ResearchMachine = ResearchEventStats & {
  machine_id: string;
  partial: boolean;
  rank: number | null;
  reason: "missing_duration" | "no_records" | null;
};
export type ResearchAnalysis = {
  mode: "deterministic_tools_only";
  model_requests: 0;
  comparison: ResearchInputs & {
    unit: "input mother rolls";
    by_machine: (ResearchInputs & { machine_id: string })[];
    recorded_dates: string[];
    missing_dates: string[];
    warnings: string[];
  };
  abnormalities: ResearchEventStats & {
    unit: "recorded event-minutes";
    rankings: ResearchMachine[];
    unranked: ResearchMachine[];
    warnings: string[];
  };
  input_explanation: string[];
  abnormality_explanation: string[];
};
