"use client";
import ReactMarkdown from "react-markdown";
import { Badge } from "@/components/ui/badge";
import { Answer } from "@/lib/api";
import DataTable from "./data-table";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
export default function AnswerView({ answer }: { answer: Answer }) {
  const categories = (
    Array.isArray(answer.verified_data.categories)
      ? answer.verified_data.categories
      : []
  ) as Record<string, unknown>[];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">{answer.mode.replaceAll("_", " ")}</Badge>
        {answer.tools.map((t) => (
          <Badge key={t} variant="secondary">
            ✓ {t}
          </Badge>
        ))}
      </div>
      <div className="prose text-sm">
        <ReactMarkdown>{answer.summary}</ReactMarkdown>
      </div>
      {Object.keys(answer.verified_data).length > 0 && (
        <div>
          <h3 className="mb-2">Verified data</h3>
          <DataTable
            rows={[
              Object.fromEntries(
                Object.entries(answer.verified_data).filter(
                  ([, value]) => !Array.isArray(value),
                ),
              ),
            ]}
          />
          {categories.length > 0 && (
            <div className="mt-5">
              <h3>Recorded abnormality minutes by reason</h3>
              <div
                style={{
                  height: Math.min(380, Math.max(180, categories.length * 42)),
                }}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={categories}
                    layout="vertical"
                    margin={{ left: 10, right: 25 }}
                  >
                    <CartesianGrid horizontal={false} />
                    <XAxis type="number" />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={145}
                      tick={{ fontSize: 10 }}
                    />
                    <Tooltip />
                    <Bar
                      dataKey="reported_minutes"
                      name="Recorded event-minutes"
                      fill="#346f9d"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <DataTable rows={categories} />
            </div>
          )}
        </div>
      )}
      {Object.keys(answer.calculations).length > 0 && (
        <div>
          <h3 className="mb-2">Python calculation</h3>
          <DataTable
            rows={[
              Object.fromEntries(
                Object.entries(answer.calculations).filter(
                  ([, v]) => !Array.isArray(v) && typeof v !== "object",
                ),
              ),
            ]}
          />
        </div>
      )}
      {answer.potential_causes.map((s) => (
        <p key={s} className="note">
          {s}
        </p>
      ))}
      {answer.recommendations.length > 0 && (
        <div>
          <h3>Review recommendations</h3>
          <ul className="mt-2 space-y-1 text-sm muted">
            {answer.recommendations.map((s) => (
              <li key={s}>• {s}</li>
            ))}
          </ul>
        </div>
      )}
      {answer.sources.length > 0 && (
        <div>
          <h3 className="mb-2">Evidence and citations</h3>
          {answer.sources.map((s, i) => (
            <div
              key={s.chunk_id || i}
              className="mb-2 rounded-lg border border-border p-3 text-sm"
            >
              <strong>
                [{i + 1}] {s.name}
              </strong>
              {s.location && <span className="ml-2 muted">{s.location}</span>}
              {s.quote && (
                <blockquote className="mt-2 whitespace-pre-wrap text-xs muted">
                  {s.quote}
                </blockquote>
              )}
              {s.scope && (
                <p className="text-xs muted">{JSON.stringify(s.scope)}</p>
              )}
            </div>
          ))}
        </div>
      )}
      {answer.assumptions.length > 0 && (
        <details className="note">
          <summary>Data sources, assumptions and limits</summary>
          <ul className="mt-2 space-y-1">
            {answer.assumptions.map((s, i) => (
              <li key={i}>• {s}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
