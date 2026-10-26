"use client";
import { ShieldCheck } from "lucide-react";
import { useWorkspace } from "../workspace";
import DataTable from "../data-table";
export default function Settings() {
  const { health } = useWorkspace();
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="panel space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} />
          <h2>Runtime and access</h2>
        </div>
        <DataTable
          rows={[
            {
              service: health?.status || "Not connected",
              model_key: health?.llm_configured
                ? "Configured on server"
                : "Not configured",
              embedding_provider: health?.embedding_provider || "Not connected",
              machine_feed: "Not connected",
              authentication: "Not implemented — localhost only",
            },
          ]}
        />
        <p className="text-sm muted">
          The account and notification controls are placeholders. This release
          is not authenticated enterprise SaaS and must stay on localhost.
        </p>
      </section>
      <section className="panel space-y-4">
        <h2>Server configuration</h2>
        <p className="text-sm muted">
          Set LLM_API_KEY or OPENAI_API_KEY, LLM_MODEL and optional LLM_BASE_URL
          in the backend environment. Never put secrets in NEXT_PUBLIC
          variables. Settings show configuration presence only.
        </p>
        <div className="note">
          No key is needed for reviewed production, scenario arithmetic, uploads
          or default local retrieval. Chroma telemetry and Agent SDK tracing are
          disabled. External calls require explicit permission.
        </div>
      </section>
    </div>
  );
}
