import type { Metadata } from "next";
import { Toaster } from "sonner";
import { generateThemeCSS } from "@/lib/theme";
import { VersionUpdateDialog } from "@/components/VersionUpdateDialog";
import "./globals.css";

export const metadata: Metadata = {
  title: "Alpaca GTT Order Tracker",
  description: "Track and manage your GTT orders",
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/favicon.png', type: 'image/png', sizes: '512x512' },
    ],
    apple: '/favicon.png',
    shortcut: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Always use production API URL via Cloudflare Tunnel
  // Tunnel is always active and routes api-trading.parthchandak.info -> localhost:8000
  // This simplifies configuration - same URL works everywhere
  const apiUrl = 'https://api-trading.parthchandak.info';
  
  return (
    <html lang="en">
      <head>
        {/* Inject theme CSS variables from theme.ts - single source of truth */}
        <style
          dangerouslySetInnerHTML={{
            __html: generateThemeCSS(),
          }}
        />
        {/* Inject API URL for runtime access in browser - must be inline and execute immediately */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                window.__API_URL__ = "${apiUrl}";
                // API URL set for runtime access
              })();
            `,
          }}
        />
      </head>
      <body>
        {children}
        <Toaster position="top-right" richColors />
        <VersionUpdateDialog />
      </body>
    </html>
  );
}
