import Screen from "@/components/screen";
export default async function Page({
  params,
}: {
  params: Promise<{ machine: string }>;
}) {
  const { machine } = await params;
  return <Screen section="production" machine={machine} />;
}
