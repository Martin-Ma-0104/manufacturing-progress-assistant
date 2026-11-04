"use client";
import { useEffect, useState } from "react";
import { Send, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, Answer } from "@/lib/api";
import AnswerView from "../answer-view";
import { useWorkspace } from "../workspace";
import ResearchAnalysis from "../research-analysis";
export default function Chat() {
  const { scope, messages, setMessages } = useWorkspace();
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
    <div className="space-y-6">
      <ResearchAnalysis />
      <div className="space-y-6">
        <section className="panel flex min-h-[480px] flex-col">
          <div className="mb-5 flex items-center justify-between border-b border-border pb-4">
            <div>
              <h2>AI chat</h2>
            </div>
          </div>
          <div className="flex-1 space-y-5 overflow-auto">
            {messages.length === 0 && (
              <div className="mx-auto max-w-xl py-16 text-center">
                <Database className="mx-auto mb-4 text-primary" size={30} />
                <h3>Ask about production</h3>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() =>
                      setText("Compare planned and actual input in this scope.")
                    }
                  >
                    Compare input
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      setText("Summarize recorded abnormalities in this scope.")
                    }
                  >
                    Analyze abnormalities
                  </Button>
                </div>
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
                Working…
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
              placeholder="Ask about production inputs or recorded abnormalities…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={1000}
              className="min-h-20"
            />
            <Button
              type="submit"
              disabled={busy || !text.trim() || (useLLM && !consent)}
              aria-label="Send question"
            >
              <Send size={16} />
            </Button>
          </form>
          <details className="mt-4 text-sm">
            <summary>AI options</summary>
            <label className="mt-3 flex items-center gap-2">
              <input
                type="checkbox"
                checked={useLLM}
                onChange={(e) => {
                  setUseLLM(e.target.checked);
                  setConsent(false);
                }}
              />
              Use AI model (API charges may apply)
            </label>
            {useLLM && (
              <label className="mt-3 flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                Allow this question and selected filters to be sent to the
                configured provider.
              </label>
            )}
          </details>
        </section>
      </div>
    </div>
  );
}
