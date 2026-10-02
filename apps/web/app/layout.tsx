import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "horse-man｜予想・買い目",
  description: "初回予想から候補を選び、最終予想・買い目と購入・見送りの判断を記録する。",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body className="antialiased">{children}</body>
    </html>
  );
}
