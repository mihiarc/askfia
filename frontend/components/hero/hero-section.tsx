"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  TreeDeciduous,
  Sparkles,
  Database,
  BarChart3,
  Leaf,
  Shield,
  ArrowRight,
  MessageSquare,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ForestBackground } from "./forest-background";
import { QueryPreviewCard } from "./query-preview-card";
import { FeaturePill } from "./feature-pill";
import { CredibilityBar } from "./credibility-bar";

interface HeroSectionProps {
  onStartExploring?: () => void;
}

export function HeroSection({ onStartExploring }: HeroSectionProps) {
  const [activeQueryIndex, setActiveQueryIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(false);

  const exampleQueries = [
    "How much forest is in Georgia?",
    "Compare timber volume in Oregon and Washington",
    "What are the top tree species in California?",
    "Show forest carbon stocks by region",
  ];

  // Rotate through example queries
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveQueryIndex((prev) => (prev + 1) % exampleQueries.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [exampleQueries.length]);

  // Trigger entrance animations
  useEffect(() => {
    setIsVisible(true);
  }, []);

  return (
    <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
      {/* Animated Forest Background */}
      <ForestBackground />

      {/* Main Content */}
      <div className="relative z-10 container mx-auto px-4 py-16 md:py-24">
        <div className="max-w-5xl mx-auto">
          {/* Top Badge */}
          <div
            className={cn(
              "flex justify-center mb-8 transition-all duration-700 delay-100",
              isVisible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            )}
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-forest-950/60 backdrop-blur-md border border-forest-700/30">
              <Shield className="h-4 w-4 text-forest-400" />
              <span className="text-sm text-forest-200">
                Official USDA Forest Service FIA Data
              </span>
            </div>
          </div>

          {/* Main Headline */}
          <div
            className={cn(
              "text-center mb-6 transition-all duration-700 delay-200",
              isVisible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            )}
          >
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight">
              <span className="text-white">Explore America&apos;s Forests</span>
              <br />
              <span className="bg-gradient-to-r from-forest-400 via-emerald-400 to-teal-400 bg-clip-text text-transparent">
                with Natural Language
              </span>
            </h1>
          </div>

          {/* Subheadline */}
          <p
            className={cn(
              "text-lg md:text-xl text-forest-100/80 text-center max-w-2xl mx-auto mb-10 transition-all duration-700 delay-300",
              isVisible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            )}
          >
            Ask questions about forest area, timber volume, biomass, and carbon
            stocks. Get instant, scientifically accurate answers powered by AI
            and the pyFIA library.
          </p>

          {/* Interactive Query Preview */}
          <div
            className={cn(
              "mb-10 transition-all duration-700 delay-400",
              isVisible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            )}
          >
            <QueryPreviewCard
              queries={exampleQueries}
              activeIndex={activeQueryIndex}
            />
          </div>

          {/* CTA Buttons */}
          <div
            className={cn(
              "flex flex-col sm:flex-row items-center justify-center gap-4 mb-16 transition-all duration-700 delay-500",
              isVisible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            )}
          >
            <Button
              size="lg"
              onClick={onStartExploring}
              className="group bg-forest-500 hover:bg-forest-400 text-white px-8 py-6 text-lg rounded-xl shadow-lg shadow-forest-500/25 hover:shadow-forest-400/30 transition-all duration-300"
            >
              <MessageSquare className="mr-2 h-5 w-5" />
              Start Exploring
              <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button
              variant="outline"
              size="lg"
              asChild
              className="px-8 py-6 text-lg rounded-xl border-forest-600/50 bg-forest-950/40 backdrop-blur-sm text-forest-100 hover:bg-forest-900/60 hover:border-forest-500/50 transition-all duration-300"
            >
              <a
                href="https://github.com/mihiarc/pyfia"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Database className="mr-2 h-5 w-5" />
                View pyFIA Library
              </a>
            </Button>
          </div>

          {/* Feature Pills */}
          <div
            className={cn(
              "flex flex-wrap justify-center gap-3 mb-12 transition-all duration-700 delay-600",
              isVisible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            )}
          >
            <FeaturePill icon={TreeDeciduous} label="Forest Area" />
            <FeaturePill icon={BarChart3} label="Timber Volume" />
            <FeaturePill icon={Leaf} label="Biomass & Carbon" />
            <FeaturePill icon={Sparkles} label="AI-Powered" />
          </div>

          {/* Stats/Credibility Section */}
          <div
            className={cn(
              "transition-all duration-700 delay-700",
              isVisible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            )}
          >
            <CredibilityBar />
          </div>
        </div>
      </div>

      {/* Bottom Gradient Fade to Content */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-background to-transparent z-20" />
    </section>
  );
}
