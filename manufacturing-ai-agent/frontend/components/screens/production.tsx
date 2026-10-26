"use client";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { fmt, query } from "@/lib/api";
import { useWorkspace } from "../workspace";
import DataTable from "../data-table";
export default function Production({ machine }: { machine?: string }) {
  const { data, scope, loading } = useWorkspace();
  if (loading || (machine && machine !== scope.machine))
    return <div className="panel">Loading historical machine records…</div>;
  if (!data) return null;
  return (
    <div className="space-y-6">
      <div className="note">
        Historical production only. Current machine state and cycle time require
        a real equipment feed; neither is inferred from output.
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {data.machines.map((m) => (
          <Link
            key={m.machine_id}
            href={
              "/production/" +
              m.machine_id +
              "?" +
              query({ ...scope, machine: m.machine_id })
            }
            className="panel block hover:border-primary"
          >
            <div className="flex justify-between">
              <h2>{m.machine_id}</h2>
              <ArrowUpRight size={16} />
            </div>
            <Badge variant="secondary" className="my-3">
              {m.status}
            </Badge>
            <div className="text-2xl font-semibold">
              {fmt(m.qualified_output_m2, "m²")}
            </div>
            <p className="mt-2 text-xs muted">
              Qualified area · {m.record_count} records
            </p>
            <p className="mt-4 text-sm">
              Plan attainment{" "}
              <strong className="float-right">{m.attainment}</strong>
            </p>
          </Link>
        ))}
      </div>
      <section className="panel">
        <h2 className="mb-4">
          Recent production history {machine && "· " + machine}
        </h2>
        <DataTable rows={data.records} />
      </section>
      <section className="panel">
        <h2 className="mb-4">Explicitly confirmed changeovers</h2>
        <DataTable rows={data.changeovers} />
      </section>
    </div>
  );
}
