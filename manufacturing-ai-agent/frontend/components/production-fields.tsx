const fields = [
  [
    "production_date / shift / machine_id / product",
    "Production date, shift, machine and product form one unique record. / 日期、班次、设备、产品共同唯一。",
  ],
  [
    "planned_rolls",
    "Planned input mother rolls / 计划投入母卷。Not a planned finished-output quantity.",
  ],
  [
    "input_rolls",
    "Actual input mother rolls / 实际投入母卷。Input attainment = sum of actual input ÷ sum of planned input.",
  ],
  [
    "qualified_rolls",
    "Qualified finished rolls / 合格成品卷。Different unit from mother rolls; do not divide these counts to infer yield.",
  ],
  [
    "actual_output_m2 / qualified_output_m2",
    "Actual / qualified output area in m² / 实际、合格产出面积。Area qualification = qualified area ÷ actual area.",
  ],
  [
    "reported_yield_pct",
    "Original reported yield (%) / 原报表综收。Optional; unknown stays blank. Its definition is not inferred.",
  ],
  [
    "source_report_date / source_shift_label / source_name / notes",
    "Source report date, original shift label, source reference and verification notes / 来源及核对信息。Stored locally alongside the record.",
  ],
];
export default function ProductionFields() {
  return (
    <details className="panel" id="database-fields">
      <summary className="cursor-pointer font-semibold">
        Database fields and units / 数据库字段与单位
      </summary>
      <p className="my-4 text-sm muted">
        Records are stored in the existing SQLite table slitting_records. No
        parallel production table is used.
      </p>
      <dl className="space-y-4">
        {fields.map(([name, description]) => (
          <div key={name}>
            <dt className="break-words font-mono text-xs">{name}</dt>
            <dd className="mt-1 text-sm muted">{description}</dd>
          </div>
        ))}
      </dl>
      <div className="note mt-5">
        <strong>Abnormality records / 异常记录</strong>
        <p className="mt-2">
          The separate abnormality_events table stores started_at, ended_at and
          reported_minutes. Recorded event minutes may overlap and are not net
          downtime. Existing runtime and utilization ranges remain estimates,
          not measured values. This form does not add or change abnormality
          events.
        </p>
      </div>
    </details>
  );
}
