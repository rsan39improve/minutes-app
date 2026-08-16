import type { Metadata } from "next";
import { IBM_Plex_Sans_JP, Bricolage_Grotesque } from "next/font/google";
import "./globals.css";

const plex = IBM_Plex_Sans_JP({
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-plex",
});

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-brand",
});

export const metadata: Metadata = {
  title: "議事録自動作成ツール",
  description: "Synclogの文字起こしを会社Word様式に整える社内ツール（Next.js版）",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body className={`${plex.variable} ${bricolage.variable}`}>{children}</body>
    </html>
  );
}
