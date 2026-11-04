"use client";
import Dashboard from "./screens/dashboard";
import Chat from "./screens/ai-expert";
import Production from "./screens/production";
export default function Screen({
  section,
  machine,
}: {
  section: string;
  machine?: string;
}) {
  switch (section) {
    case "dashboard":
      return <Dashboard />;
    case "ai-expert":
      return <Chat />;
    case "production":
      return <Production machine={machine} />;
    default:
      return null;
  }
}
