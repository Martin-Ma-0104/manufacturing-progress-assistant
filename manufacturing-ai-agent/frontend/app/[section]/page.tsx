import Screen from "@/components/screen";
import { notFound } from "next/navigation";
const sections = [
  "dashboard",
  "ai-expert",
  "production",
  "planning",
  "inventory",
  "knowledge",
  "settings",
];
export const dynamicParams = false;
export function generateStaticParams() {
  return sections.map((section) => ({ section }));
}
export default async function Page({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (
    ![
      "dashboard",
      "ai-expert",
      "production",
      "planning",
      "inventory",
      "knowledge",
      "settings",
    ].includes(section)
  )
    notFound();
  return <Screen section={section} />;
}
