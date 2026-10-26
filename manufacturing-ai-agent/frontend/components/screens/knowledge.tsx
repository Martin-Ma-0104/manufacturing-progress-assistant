"use client";
import { FormEvent, useEffect, useState } from "react";
import { FileText, Upload, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, Doc } from "@/lib/api";
import { useWorkspace } from "../workspace";
import DataTable from "../data-table";
export default function Knowledge() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [permission, setPermission] = useState(false);
  const { health } = useWorkspace();
  const reload = () =>
    api<{ documents: Doc[] }>("/knowledge/documents").then((d) =>
      setDocs(d.documents),
    );
  useEffect(() => {
    reload().catch((e) => setError(e.message));
  }, []);
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const data = new FormData(form);
      data.set("allow_external", String(permission));
      const r = await api<{ duplicate: boolean; chunks?: number }>(
        "/knowledge/documents",
        data,
      );
      setMessage(
        r.duplicate
          ? "Document already indexed; duplicate skipped."
          : `Indexed ${r.chunks} chunks with source locations.`,
      );
      await reload();
      form.reset();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reindex(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(
        "/knowledge/documents/" + id + "/reindex?allow_external=" + permission,
        {},
      );
      await reload();
      setMessage("Document reindexed from retained extracted text.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-6">
      <div className="note">
        Knowledge storage is separate from production SQLite. Default provider:{" "}
        <strong>{health?.embedding_provider || "local-hash-v1"}</strong>. Local
        hashing uses lexical vectors, not a learned semantic model; no model
        download or external document transfer occurs by default.
      </div>
      <form onSubmit={upload} className="panel space-y-5">
        <div className="flex justify-between">
          <div>
            <h2>Index a manufacturing document</h2>
            <p className="text-xs muted">
              PDF, DOCX, TXT or Markdown · maximum 5 MiB · text-based documents
              only
            </p>
          </div>
          <Upload size={20} className="text-primary" />
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <label htmlFor="document">Document</label>
            <Input
              id="document"
              name="file"
              type="file"
              accept=".pdf,.docx,.txt,.md"
              required
            />
          </div>
          <div>
            <label htmlFor="doc-category">Category</label>
            <select id="doc-category" name="category">
              {[
                "Production SOP",
                "Quality Standards",
                "Equipment Manuals",
                "Maintenance Procedures",
                "Troubleshooting Guidelines",
                "Product Specifications",
                "Manufacturing Process Knowledge",
              ].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>
        {health?.embedding_provider === "openai" && (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={permission}
              onChange={(e) => setPermission(e.target.checked)}
            />
            Allow this document to be sent to OpenAI for embeddings. Charges may
            apply.
          </label>
        )}
        <div className="flex flex-wrap items-center gap-4">
          <Button disabled={busy}>
            <Upload size={15} />
            {busy ? "Extracting and indexing…" : "Upload and index"}
          </Button>
          <a
            href="/sample-sop.md"
            download
            className="text-xs text-primary underline"
          >
            Download a synthetic SOP to try
          </a>
        </div>
        {error && (
          <p role="alert" className="note">
            {error}
          </p>
        )}
        {message && (
          <p role="status" className="note">
            {message}
          </p>
        )}
      </form>
      <section className="panel">
        <div className="mb-5 flex items-center justify-between">
          <h2>Indexed documents</h2>
          <Badge variant="outline">{docs.length} documents</Badge>
        </div>
        {docs.length ? (
          <div className="space-y-3">
            {docs.map((d) => (
              <div
                key={d.id}
                className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border p-4"
              >
                <div className="flex gap-3">
                  <FileText size={20} className="text-primary" />
                  <div>
                    <strong className="text-sm">{d.name}</strong>
                    <p className="text-xs muted">
                      {d.category} · {d.chunks} chunks · {d.provider}
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  onClick={() => void reindex(d.id)}
                >
                  <RefreshCw size={13} />
                  Reindex
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <div className="note">
            No documents indexed. Upload the synthetic SOP, then ask the AI
            Production Expert about its cleaning checklist.
          </div>
        )}
      </section>
    </div>
  );
}
