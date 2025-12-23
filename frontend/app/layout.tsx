import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/providers/auth-provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Forest Inventory Explorer",
  description:
    "Natural language interface to USDA Forest Service FIA data, powered by pyFIA",
  keywords: [
    "forest inventory",
    "FIA",
    "USDA Forest Service",
    "timber",
    "biomass",
    "carbon",
  ],
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
          <header className="border-b bg-card">
            <div className="container mx-auto px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🌲</span>
                <h1 className="text-xl font-semibold text-foreground">
                  Forest Inventory Explorer
                </h1>
              </div>
              <nav className="flex items-center gap-4">
                <a
                  href="https://github.com/mihiarc/pyfia"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  pyFIA
                </a>
                <a
                  href="https://www.fia.fs.usda.gov/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  FIA Program
                </a>
              </nav>
            </div>
          </header>
          <main>
            <AuthProvider>{children}</AuthProvider>
          </main>
        </div>
      </body>
    </html>
  );
}
