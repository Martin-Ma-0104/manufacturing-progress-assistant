"use client";
import { FormEvent, useState } from "react";
import { Calculator } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, fmt, Capacity } from "@/lib/api";
import { useWorkspace } from "../workspace";
import DataTable from "../data-table";
export default function Planning() {
  const [value, setValue] = useState<Capacity>({
    available_minutes: 480,
    cycle_minutes: 30,
    machines: 1,
    downtime_minutes: 0,
    units_per_cycle: 1,
    output_unit: "cycles",
    expected_yield: 0.9,
  });
  const [targetCT, setTargetCT] = useState(27);
  const [target, setTarget] = useState(100);
  const [result, setResult] = useState<Record<string, unknown>>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function calculate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(
        await api("/planning/compare", {
          baseline: value,
          alternative: { ...value, cycle_minutes: targetCT },
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const baseline = result?.baseline as Record<string, unknown> | undefined,
    alternative = result?.alternative as Record<string, unknown> | undefined;
  return (
    <div className="space-y-6">
      <div className="note">
        SCENARIO WORKSPACE — entered assumptions, not measured capacity or a
        live work order. No globally optimal scheduling is claimed.
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <form className="panel space-y-5" onSubmit={calculate}>
          <h2>Compare operating assumptions</h2>
          <div className="grid gap-5 sm:grid-cols-2">
            {[
              ["available_minutes", "Available minutes / machine"],
              ["cycle_minutes", "Baseline cycle time (minutes)"],
              ["machines", "Identical scenario machines"],
              ["downtime_minutes", "Expected downtime minutes / machine"],
              ["units_per_cycle", "Output units / cycle"],
              ["expected_yield", "Expected yield (0–1)"],
            ].map(([key, label]) => (
              <div key={key}>
                <label htmlFor={key}>{label}</label>
                <Input
                  id={key}
                  type="number"
                  step={key === "machines" ? 1 : "any"}
                  min={
                    key === "cycle_minutes" || key === "units_per_cycle"
                      ? 0.001
                      : key === "machines"
                        ? 1
                        : 0
                  }
                  max={key === "expected_yield" ? 1 : undefined}
                  value={value[key as keyof Capacity]}
                  onChange={(e) => {
                    setResult(undefined);
                    setValue({ ...value, [key]: Number(e.target.value) });
                  }}
                />
              </div>
            ))}
            <div>
              <label htmlFor="out-unit">Output unit</label>
              <select
                id="out-unit"
                value={value.output_unit}
                onChange={(e) => {
                  setResult(undefined);
                  setValue({ ...value, output_unit: e.target.value });
                }}
              >
                <option value="cycles">Cycles</option>
                <option value="finished_rolls">Finished rolls</option>
                <option value="m2">m²</option>
              </select>
            </div>
            <div>
              <label htmlFor="target-ct">
                Alternative cycle time (minutes)
              </label>
              <Input
                id="target-ct"
                type="number"
                min=".001"
                step="any"
                value={targetCT}
                onChange={(e) => {
                  setResult(undefined);
                  setTargetCT(Number(e.target.value));
                }}
              />
            </div>
          </div>
          <Button disabled={busy}>
            <Calculator size={16} />
            {busy ? "Calculating…" : "Compare scenarios"}
          </Button>
          {error && (
            <p role="alert" className="note">
              {error}
            </p>
          )}
        </form>
        <section className="panel space-y-4">
          <Badge variant="outline">DEMO work-order draft</Badge>
          <h2>Target and specifications</h2>
          <label htmlFor="target-quantity">Scenario target quantity</label>
          <Input
            id="target-quantity"
            type="number"
            min="0"
            value={target}
            onChange={(e) => setTarget(Number(e.target.value))}
          />
          <Input
            aria-label="Scenario product specification"
            placeholder="Enter an assumed product specification"
          />
          <p className="text-xs muted">
            Session-only inputs. Real work-order storage, machine capability,
            calendars, priorities and inventory constraints are not connected.
            Scenario machines are identical virtual resources, not a recommended
            FX allocation.
          </p>
        </section>
      </div>
      {result && baseline && alternative && (
        <section className="panel space-y-4">
          <h2>Deterministic Python results</h2>
          <DataTable
            rows={[
              {
                scenario: "Baseline",
                completed_cycles: baseline.estimated_cycles,
                qualified_output: baseline.estimated_qualified_output,
                unit: baseline.output_unit,
              },
              {
                scenario: "Alternative",
                completed_cycles: alternative.estimated_cycles,
                qualified_output: alternative.estimated_qualified_output,
                unit: alternative.output_unit,
              },
            ]}
          />
          <p className="text-sm">
            Change in qualified scenario output:{" "}
            <strong>
              {fmt(result.output_change)} {value.output_unit}
            </strong>
          </p>
          <p className="text-xs muted">
            Target is {target.toLocaleString()} {value.output_unit}; feasibility
            depends on the entered assumptions, not a promised completion date.
          </p>
          <div className="note">
            Complete cycles are floored separately for each machine. Available
            time minus stated downtime determines effective minutes. Qualified
            output = cycles × units per cycle × stated yield. No recorded
            abnormality sum is automatically deducted.
          </div>
        </section>
      )}
    </div>
  );
}
