import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/providers/auth-provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Forest Inventory Explorer",
  description:
    "AI-powered natural language interface to USDA Forest Service FIA data. Query forest area, timber volume, biomass, and carbon stocks with simple questions.",
  keywords: [
    "forest inventory",
    "FIA",
    "USDA Forest Service",
    "timber",
    "biomass",
    "carbon",
    "AI",
    "natural language",
    "pyFIA",
  ],
  openGraph: {
    title: "Forest Inventory Explorer",
    description:
      "Explore America's forests with natural language. AI-powered queries for forest area, timber volume, biomass, and carbon stocks.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <div className="min-h-screen bg-background">
          <main>
            <AuthProvider>{children}</AuthProvider>
          </main>
        </div>
      </body>
    </html>
  );
}
