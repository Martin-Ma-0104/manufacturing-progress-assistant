"use client";
import Dashboard from "./screens/dashboard";
import Chat from "./screens/ai-expert";
import Production from "./screens/production";
import Planning from "./screens/planning";
import Inventory from "./screens/inventory";
import Knowledge from "./screens/knowledge";
import Settings from "./screens/settings";
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
    case "planning":
      return <Planning />;
    case "inventory":
      return <Inventory />;
    case "knowledge":
      return <Knowledge />;
    case "settings":
      return <Settings />;
    default:
      return null;
  }
}
