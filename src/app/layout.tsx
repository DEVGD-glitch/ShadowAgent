import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { TauriSplashScreen } from "@/components/tauri/splash-screen";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Shadow Agent — Your AI Companion",
  description: "Shadow Agent is your personal AI companion that thinks, learns, and evolves with you.",
  keywords: ["Shadow Agent", "AI Agent", "LLM", "Automation", "Self-evolving", "Desktop AI"],
  authors: [{ name: "Shadow Agent Team" }],
  icons: {
    icon: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <TauriSplashScreen />
        {children}
        <Toaster />
      </body>
    </html>
  );
}
