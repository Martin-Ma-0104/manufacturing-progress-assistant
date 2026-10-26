import type { Metadata } from "next";
import Workspace from "@/components/workspace";
import "./globals.css";
export const metadata: Metadata = {
  title: "Manufacturing AI — Operations",
  description:
    "Local manufacturing analysis, scenario tools and source-grounded knowledge.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Workspace>{children}</Workspace>
      </body>
    </html>
  );
}
