import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/query-provider";
import { Auth0Provider } from "@auth0/nextjs-auth0/client";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PolicyDiff — Medical Benefit Drug Policy Tracker",
  description: "AI-powered medical benefit drug policy intelligence engine.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans h-full bg-background text-primary-text antialiased`}>
        <Auth0Provider>
          <QueryProvider>
            {children}
          </QueryProvider>
        </Auth0Provider>
      </body>
    </html>
  );
}
