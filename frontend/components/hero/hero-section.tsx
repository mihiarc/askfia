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

// Animated Forest Background with SVG Trees and Particles
function ForestBackground() {
  return (
    <div className="absolute inset-0">
      {/* Base gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-forest-950 via-forest-900 to-forest-950" />

      {/* Radial glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-forest-800/30 via-transparent to-transparent" />

      {/* Animated gradient orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl animate-pulse-slow" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-teal-500/10 rounded-full blur-3xl animate-pulse-slower" />

      {/* Grid pattern overlay */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)
          `,
          backgroundSize: "50px 50px",
        }}
      />

      {/* Floating particles */}
      <FloatingParticles />

      {/* SVG Tree Silhouettes */}
      <TreeSilhouettes />

      {/* Data visualization lines */}
      <DataVisualization />
    </div>
  );
}

// Floating leaf/data particles - reduced count for performance
function FloatingParticles() {
  // Reduced from 20 to 8 particles for better performance
  const particles = Array.from({ length: 8 }, (_, i) => ({
    id: i,
    left: `${10 + (i * 12)}%`, // More evenly distributed
    delay: `${i * 0.8}s`,
    duration: `${18 + (i % 3) * 4}s`,
    size: i % 2 === 0 ? "w-1 h-1" : "w-1.5 h-1.5",
  }));

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((particle) => (
        <div
          key={particle.id}
          className={cn(
            "absolute rounded-full bg-forest-400/30 animate-float-up will-change-transform",
            particle.size
          )}
          style={{
            left: particle.left,
            bottom: "-20px",
            animationDelay: particle.delay,
            animationDuration: particle.duration,
          }}
        />
      ))}
    </div>
  );
}

// Tree silhouettes at bottom
function TreeSilhouettes() {
  return (
    <div className="absolute bottom-0 left-0 right-0 h-64 overflow-hidden opacity-40">
      <svg
        viewBox="0 0 1200 200"
        className="absolute bottom-0 w-full h-auto"
        preserveAspectRatio="xMidYMax slice"
      >
        {/* Far trees - lighter */}
        <g className="fill-forest-800">
          <path d="M0,200 L0,120 L30,60 L60,120 L60,200 Z" />
          <path d="M80,200 L80,100 L120,30 L160,100 L160,200 Z" />
          <path d="M200,200 L200,130 L235,80 L270,130 L270,200 Z" />
          <path d="M320,200 L320,110 L370,40 L420,110 L420,200 Z" />
          <path d="M480,200 L480,125 L520,65 L560,125 L560,200 Z" />
          <path d="M600,200 L600,115 L650,50 L700,115 L700,200 Z" />
          <path d="M750,200 L750,130 L790,75 L830,130 L830,200 Z" />
          <path d="M880,200 L880,105 L930,35 L980,105 L980,200 Z" />
          <path d="M1020,200 L1020,120 L1060,60 L1100,120 L1100,200 Z" />
          <path d="M1140,200 L1140,135 L1170,90 L1200,135 L1200,200 Z" />
        </g>

        {/* Near trees - darker */}
        <g className="fill-forest-900">
          <path d="M-20,200 L-20,140 L20,90 L60,140 L60,200 Z" />
          <path d="M100,200 L100,130 L155,60 L210,130 L210,200 Z" />
          <path d="M260,200 L260,150 L300,110 L340,150 L340,200 Z" />
          <path d="M400,200 L400,120 L460,50 L520,120 L520,200 Z" />
          <path d="M580,200 L580,145 L630,85 L680,145 L680,200 Z" />
          <path d="M720,200 L720,135 L775,70 L830,135 L830,200 Z" />
          <path d="M900,200 L900,150 L940,100 L980,150 L980,200 Z" />
          <path d="M1040,200 L1040,125 L1100,55 L1160,125 L1160,200 Z" />
        </g>
      </svg>
    </div>
  );
}

// Animated data visualization lines
function DataVisualization() {
  return (
    <div className="absolute inset-0 overflow-hidden opacity-20">
      <svg
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px]"
        viewBox="0 0 800 400"
      >
        {/* Animated line chart */}
        <path
          d="M0,300 Q100,250 200,280 T400,200 T600,250 T800,180"
          fill="none"
          stroke="url(#lineGradient)"
          strokeWidth="2"
          className="animate-draw-line"
          strokeDasharray="1000"
          strokeDashoffset="1000"
        />

        {/* Data points */}
        <circle cx="200" cy="280" r="4" className="fill-forest-400 animate-pulse-slow" />
        <circle cx="400" cy="200" r="4" className="fill-emerald-400 animate-pulse-slower" />
        <circle cx="600" cy="250" r="4" className="fill-teal-400 animate-pulse-slow" />

        {/* Gradient definition */}
        <defs>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.3" />
            <stop offset="50%" stopColor="#10b981" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#14b8a6" stopOpacity="0.3" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}

// Interactive query preview card
function QueryPreviewCard({
  queries,
  activeIndex,
}: {
  queries: string[];
  activeIndex: number;
}) {
  return (
    <div className="max-w-2xl mx-auto">
      {/* Glassmorphism card */}
      <div className="relative rounded-2xl bg-forest-950/60 backdrop-blur-xl border border-forest-700/30 shadow-2xl shadow-black/20 overflow-hidden">
        {/* Header bar */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-forest-700/30 bg-forest-900/40">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/70" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
            <div className="w-3 h-3 rounded-full bg-green-500/70" />
          </div>
          <div className="flex-1 flex justify-center">
            <span className="text-xs text-forest-400/60 font-mono">
              Forest Inventory Explorer
            </span>
          </div>
        </div>

        {/* Query content */}
        <div className="p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-forest-600 flex items-center justify-center shrink-0">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-forest-300 mb-2">Try asking:</p>
              <div className="relative h-8 overflow-hidden">
                {queries.map((query, index) => (
                  <p
                    key={index}
                    className={cn(
                      "absolute inset-0 text-lg md:text-xl font-medium text-white transition-all duration-500",
                      index === activeIndex
                        ? "opacity-100 translate-y-0"
                        : "opacity-0 translate-y-4"
                    )}
                  >
                    &ldquo;{query}&rdquo;
                  </p>
                ))}
              </div>
            </div>
          </div>

          {/* Query indicator dots */}
          <div className="flex justify-center gap-2">
            {queries.map((_, index) => (
              <div
                key={index}
                className={cn(
                  "w-2 h-2 rounded-full transition-all duration-300",
                  index === activeIndex
                    ? "bg-forest-400 w-6"
                    : "bg-forest-700"
                )}
              />
            ))}
          </div>
        </div>

        {/* Subtle shine effect */}
        <div className="absolute inset-0 bg-gradient-to-br from-white/5 via-transparent to-transparent pointer-events-none" />
      </div>
    </div>
  );
}

// Feature pill component
function FeaturePill({
  icon: Icon,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-forest-900/50 backdrop-blur-sm border border-forest-700/30 text-forest-200 text-sm transition-all duration-300 hover:bg-forest-800/50 hover:border-forest-600/40">
      <Icon className="h-4 w-4 text-forest-400" />
      <span>{label}</span>
    </div>
  );
}

// Credibility bar with stats and logos
function CredibilityBar() {
  return (
    <div className="flex flex-col items-center">
      <p className="text-forest-400/60 text-sm mb-4 uppercase tracking-wider">
        Trusted Data Sources
      </p>

      <div className="flex flex-wrap items-center justify-center gap-8 md:gap-12">
        {/* USDA Forest Service */}
        <div className="flex items-center gap-2 text-forest-300/70 hover:text-forest-200 transition-colors">
          <Shield className="h-5 w-5" />
          <span className="text-sm font-medium">USDA Forest Service</span>
        </div>

        {/* Divider */}
        <div className="hidden md:block w-px h-6 bg-forest-700/50" />

        {/* FIA Program */}
        <div className="flex items-center gap-2 text-forest-300/70 hover:text-forest-200 transition-colors">
          <Database className="h-5 w-5" />
          <span className="text-sm font-medium">FIA National Program</span>
        </div>

        {/* Divider */}
        <div className="hidden md:block w-px h-6 bg-forest-700/50" />

        {/* pyFIA */}
        <div className="flex items-center gap-2 text-forest-300/70 hover:text-forest-200 transition-colors">
          <TreeDeciduous className="h-5 w-5" />
          <span className="text-sm font-medium">Validated with pyFIA</span>
        </div>
      </div>

      {/* Stats row */}
      <div className="flex flex-wrap items-center justify-center gap-8 mt-8 pt-6 border-t border-forest-800/50">
        <StatItem value="50" label="States Covered" />
        <StatItem value="300K+" label="Plot Samples" />
        <StatItem value="20+" label="Years of Data" />
        <StatItem value="100%" label="Open Source" />
      </div>
    </div>
  );
}

// Stat item component
function StatItem({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <p className="text-2xl md:text-3xl font-bold text-forest-300">{value}</p>
      <p className="text-xs text-forest-400/60 uppercase tracking-wider">
        {label}
      </p>
    </div>
  );
}
