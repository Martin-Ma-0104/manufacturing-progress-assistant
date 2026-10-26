"use client";
import { useEffect, useState } from "react";
import { ArrowUpRight, Send, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { api, Answer } from "@/lib/api";
import AnswerView from "../answer-view";
import { useWorkspace } from "../workspace";
import DataTable from "../data-table";
export default function Chat() {
  const { scope, health, messages, setMessages } = useWorkspace();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [useLLM, setUseLLM] = useState(false);
  const [consent, setConsent] = useState(false);
  useEffect(() => {
    setConsent(false);
  }, [scope]);
  async function send(value = text) {
    if (!value.trim() || busy) return;
    setText("");
    setError("");
    setMessages((m) => [...m, { role: "user", text: value }]);
    setBusy(true);
    try {
      const answer = await api<Answer>("/agent/chat", {
        message: value,
        scope: Object.fromEntries(
          Object.entries(scope).filter(([, v]) => v !== ""),
        ),
        use_llm: useLLM,
        allow_external: consent,
      });
      setMessages((m) => [
        ...m,
        { role: "assistant", text: answer.summary, answer },
      ]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
      <section className="panel flex min-h-[620px] flex-col">
        <div className="mb-5 flex items-center justify-between border-b border-border pb-4">
          <div>
            <h2>AI Production Expert</h2>
            <p className="text-xs muted">
              One shared Python tool layer · read-only manufacturing support
            </p>
          </div>
          <Badge variant="outline">
            {health?.llm_configured
              ? "API configured"
              : "Local tools available"}
          </Badge>
        </div>
        <div className="flex-1 space-y-5 overflow-auto">
          {messages.length === 0 && (
            <div className="mx-auto max-w-xl py-16 text-center">
              <Database className="mx-auto mb-4 text-primary" size={30} />
              <h2>Start with a concrete production question</h2>
              <p className="mt-3 text-sm muted">
                Calculate a stated scenario, inspect reviewed records, or
                retrieve indexed SOP evidence. Unknown data stays unknown.
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[85%] rounded-xl bg-secondary p-4 text-sm"
                  : "rounded-xl border border-border p-5"
              }
            >
              <div className="eyebrow mb-3">
                {m.role === "user" ? "You" : "Production expert"}
              </div>
              {m.answer ? <AnswerView answer={m.answer} /> : m.text}
            </div>
          ))}
          {busy && (
            <p role="status" className="text-sm muted animate-pulse">
              Validating scope and executing read-only tools…
            </p>
          )}
        </div>
        {error && (
          <p role="alert" className="note my-3">
            {error}
          </p>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
          className="mt-5 flex items-end gap-3 border-t border-border pt-5"
        >
          <Textarea
            aria-label="Manufacturing question"
            placeholder="Ask about the selected scope, a capacity scenario, or an SOP…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={1000}
            className="min-h-20"
          />
          <Button
            type="submit"
            disabled={
              busy ||
              !text.trim() ||
              ((useLLM || health?.embedding_provider === "openai") && !consent)
            }
            aria-label="Send question"
          >
            <Send size={16} />
          </Button>
        </form>
      </section>
      <aside className="space-y-5">
        <section className="panel">
          <h3>Suggested questions</h3>
          {[
            "Summarize production and abnormality evidence in this scope.",
            "Capacity for 2 machines over 8 hours at CT 27 minutes?",
            "What does the SOP say about machine cleaning?",
          ].map((q) => (
            <button
              key={q}
              onClick={() => setText(q)}
              className="mt-4 block text-left text-xs leading-6 text-primary"
            >
              {q}
              <ArrowUpRight size={12} className="ml-1 inline" />
            </button>
          ))}
        </section>
        <section className="panel text-xs">
          <h3>Model access</h3>
          <label className="mt-4 flex items-center gap-2">
            <input
              type="checkbox"
              checked={useLLM}
              onChange={(e) => {
                setUseLLM(e.target.checked);
                setConsent(false);
              }}
            />
            Use configured LLM for tool selection
          </label>
          {(useLLM || health?.embedding_provider === "openai") && (
            <label className="mt-3 flex items-start gap-2">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              Allow this question and current scope to be sent to the configured
              provider. If OpenAI embeddings are enabled, also allow this
              question to be sent to OpenAI for retrieval.
            </label>
          )}
          <p className="mt-3 muted">
            Without a key, local tools and extractive knowledge answers work.
            Document text is not sent to the LLM. Model calls may incur charges.
          </p>
        </section>
        <section className="note">
          No equipment control, work-order writes, inventory transactions or
          automatic purchasing. Correlation is not demonstrated root cause.
        </section>
      </aside>
    </div>
  );
}
