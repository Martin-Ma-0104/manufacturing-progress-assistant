"use client";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useWorkspace } from "../workspace";
import DataTable from "../data-table";
export default function Inventory() {
  const [target, setTarget] = useState(1000);
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setError("");
    api<{ items: Record<string, unknown>[] }>(
      "/inventory?planned_quantity=" + target,
    )
      .then((d) => {
        if (active) setItems(d.items);
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setItems([]);
        }
      });
    return () => {
      active = false;
    };
  }, [target]);
  return (
    <div className="space-y-6">
      <div className="note font-semibold">
        SYNTHETIC INVENTORY — no ERP/MES inventory is connected. No stock
        transactions or purchasing actions are available.
      </div>
      <section className="panel">
        <h2>Material coverage scenario</h2>
        <p className="mb-4 text-sm muted">
          Example BOM: 0.5 kg demo resin per finished roll. These are explicitly
          synthetic assumptions.
        </p>
        <div className="max-w-xs">
          <label htmlFor="demo-target">Planned finished rolls (demo)</label>
          <Input
            id="demo-target"
            type="number"
            min="0"
            max="1000000"
            value={target}
            onChange={(e) => setTarget(Number(e.target.value))}
          />
        </div>
        {error && <p role="alert">{error}</p>}
        <div className="mt-5">
          <DataTable rows={items} />
        </div>
      </section>
      <section className="panel">
        <h2>Real inventory readiness</h2>
        <p className="mt-3 text-sm muted">
          Connect reviewed stock balances, reservations, receipts, material
          units and effective BOM revisions before enabling real material
          requirements. Coverage in this demo is finished-roll equivalent, not
          days of coverage.
        </p>
      </section>
    </div>
  );
}
