"use client";

import { cn } from "@/lib/utils";

/**
 * Animated forest background with gradient orbs, particles, and tree silhouettes.
 */
export function ForestBackground() {
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

/**
 * Floating leaf/data particles - reduced count for performance.
 */
function FloatingParticles() {
  // Reduced from 20 to 8 particles for better performance
  const particles = Array.from({ length: 8 }, (_, i) => ({
    id: i,
    left: `${10 + i * 12}%`, // More evenly distributed
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

/**
 * Tree silhouettes at bottom of the hero section.
 */
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

/**
 * Animated data visualization lines with chart and data points.
 */
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
        <circle
          cx="200"
          cy="280"
          r="4"
          className="fill-forest-400 animate-pulse-slow"
        />
        <circle
          cx="400"
          cy="200"
          r="4"
          className="fill-emerald-400 animate-pulse-slower"
        />
        <circle
          cx="600"
          cy="250"
          r="4"
          className="fill-teal-400 animate-pulse-slow"
        />

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
