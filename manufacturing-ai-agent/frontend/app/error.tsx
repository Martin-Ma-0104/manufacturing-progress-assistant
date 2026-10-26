"use client";
import { Button } from "@/components/ui/button";
export default function Error({ reset }: { reset: () => void }) {
  return (
    <section className="panel">
      <h2>This view could not be loaded</h2>
      <p className="muted">
        Your data has not been modified. Retry or use the Streamlit fallback.
      </p>
      <Button onClick={reset}>Try again</Button>
    </section>
  );
}
