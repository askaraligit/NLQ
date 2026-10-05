import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "NLQ · Your analytics workspace", template: "%s · NLQ" },
  description: "A workspace for exploring your business data through natural language.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
