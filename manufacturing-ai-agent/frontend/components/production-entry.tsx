"use client";
import { FormEvent, useEffect, useState } from "react";
import { api, Scope } from "@/lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";

type Saved = {
  status: "saved" | "unchanged";
  production_date: string;
  machine_id: string;
  shift: "Day" | "Night";
  product: string;
};
const counts = [
  [
    "planned_rolls",
    "Planned input / 计划投入母卷",
    "mother rolls",
    "2147483647",
    "1",
  ],
  [
    "input_rolls",
    "Actual input / 实际投入母卷",
    "mother rolls",
    "2147483647",
    "1",
  ],
  [
    "qualified_rolls",
    "Qualified finished rolls / 合格成品卷",
    "finished rolls",
    "2147483647",
    "1",
  ],
  [
    "actual_output_m2",
    "Actual output area / 实际产出面积",
    "m²",
    "1000000000000",
    "any",
  ],
  [
    "qualified_output_m2",
    "Qualified output area / 合格产出面积",
    "m²",
    "1000000000000",
    "any",
  ],
] as const;
export default function ProductionEntry({
  scope,
  fixedMachine,
  onSaved,
}: {
  scope: Scope;
  fixedMachine?: string;
  onSaved: (scope: Scope) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  useEffect(() => {
    if (window.location.hash === "#entry") setOpen(true);
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) || "").trim();
    const payload = {
      source: "reviewed",
      confirmed_real: form.get("confirmed_real") === "on",
      production_date: text("production_date"),
      shift: text("shift"),
      machine_id: text("machine_id"),
      product: text("product"),
      planned_rolls: Number(text("planned_rolls")),
      input_rolls: Number(text("input_rolls")),
      qualified_rolls: Number(text("qualified_rolls")),
      actual_output_m2: Number(text("actual_output_m2")),
      qualified_output_m2: Number(text("qualified_output_m2")),
      reported_yield_pct:
        text("reported_yield_pct") === ""
          ? null
          : Number(text("reported_yield_pct")),
      source_report_date: text("source_report_date"),
      source_shift_label: text("source_shift_label"),
      source_name: text("source_name"),
      notes: text("notes"),
    };
    if (payload.qualified_output_m2 > payload.actual_output_m2) {
      setError(
        "Qualified area cannot exceed actual output area / 合格面积不能超过实际产出面积。",
      );
      return;
    }
    setBusy(true);
    try {
      const saved = await api<Saved>("/production/records", payload);
      setSuccess(
        saved.status === "saved"
          ? "Saved to the actual production database. The records below now show this date, machine, shift and product. / 已保存，下方显示对应记录。"
          : "Identical record already exists; no duplicate was added. / 相同记录已存在，未重复添加。",
      );
      onSaved({
        ...scope,
        source: "reviewed",
        start: saved.production_date,
        end: saved.production_date,
        machine: saved.machine_id,
        shift: saved.shift,
        product: saved.product,
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Save failed. Your entries have been kept.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel space-y-4" id="entry">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2>Real production records / 真实生产记录</h2>
          <p className="mt-1 text-sm muted">
            Enter verified figures from a production report. Blank values are
            not treated as zero.
          </p>
        </div>
        <Button
          type="button"
          aria-expanded={open}
          aria-controls="entry-form"
          onClick={() => setOpen(!open)}
        >
          {open ? "Close form / 收起" : "Add real record / 录入真实数据"}
        </Button>
      </div>
      {success && (
        <p role="status" className="note">
          {success}
        </p>
      )}
      {open && (
        <form id="entry-form" onSubmit={submit} className="space-y-5">
          <p className="note">
            One row = production date + shift + machine + product. Use the
            report’s confirmed production date; do not automatically move night
            shifts to another day. This form adds records; it never overwrites
            an existing record.
          </p>
          <fieldset
            disabled={busy}
            className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          >
            <div>
              <label htmlFor="entry-date">Production date / 生产归属日期</label>
              <Input
                id="entry-date"
                name="production_date"
                type="date"
                required
                defaultValue={scope.end}
              />
            </div>
            <div>
              <label htmlFor="entry-shift">Shift / 班次</label>
              <select
                id="entry-shift"
                name="shift"
                required
                defaultValue={scope.shift === "All" ? "" : scope.shift}
              >
                <option value="">Select shift</option>
                <option value="Day">Day / 白班</option>
                <option value="Night">Night / 夜班</option>
              </select>
            </div>
            <div>
              <label htmlFor="entry-machine">Machine ID / 设备编号</label>
              <Input
                id="entry-machine"
                name="machine_id"
                required
                maxLength={128}
                pattern="[A-Za-z0-9_\-]+"
                defaultValue={fixedMachine || scope.machine}
                readOnly={!!fixedMachine}
              />
            </div>
            <div className="md:col-span-2">
              <label htmlFor="entry-product">Product / 产品规格</label>
              <Input
                id="entry-product"
                name="product"
                required
                maxLength={256}
                defaultValue={scope.product}
              />
            </div>
            {counts.map(([name, label, unit, max, step]) => (
              <div key={name}>
                <label htmlFor={"entry-" + name}>
                  {label} ({unit})
                </label>
                <Input
                  id={"entry-" + name}
                  name={name}
                  type="number"
                  min="0"
                  max={max}
                  step={step}
                  required
                />
              </div>
            ))}
            <div>
              <label htmlFor="entry-yield">
                Reported yield / 原报表综收 (%) — optional
              </label>
              <Input
                id="entry-yield"
                name="reported_yield_pct"
                type="number"
                min="0"
                max="100"
                step="any"
              />
              <p className="mt-1 text-xs muted">
                Leave blank if unknown. Do not infer from roll counts.
              </p>
            </div>
            <div>
              <label htmlFor="entry-report-date">
                Source report date / 原报表日期
              </label>
              <Input
                id="entry-report-date"
                name="source_report_date"
                type="date"
                required
              />
            </div>
            <div>
              <label htmlFor="entry-source-shift">
                Original shift label / 原班次标签
              </label>
              <Input
                id="entry-source-shift"
                name="source_shift_label"
                required
                maxLength={128}
              />
            </div>
            <div>
              <label htmlFor="entry-source">Source reference / 来源名称</label>
              <Input
                id="entry-source"
                name="source_name"
                required
                maxLength={256}
              />
              <p className="mt-1 text-xs muted">
                A report name or reference; no file upload needed.
              </p>
            </div>
            <div className="md:col-span-2 xl:col-span-3">
              <label htmlFor="entry-notes">
                Verification notes / 核对备注 — optional
              </label>
              <Textarea id="entry-notes" name="notes" maxLength={4000} />
            </div>
            <div className="md:col-span-2 xl:col-span-3">
              <label
                className="flex items-start gap-2 text-sm"
                htmlFor="entry-confirm"
              >
                <input
                  id="entry-confirm"
                  name="confirmed_real"
                  type="checkbox"
                  required
                  className="mt-1"
                />
                I verified these actual production figures, units, date and
                shift against the source report. /
                我已核对真实数据、单位、日期和班次。
              </label>
            </div>
            <Button type="submit" className="w-fit">
              {busy ? "Saving…" : "Save real record / 保存真实记录"}
            </Button>
          </fieldset>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </form>
      )}
    </section>
  );
}
