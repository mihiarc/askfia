"use client";

import { Shield, Database, TreeDeciduous } from "lucide-react";

/**
 * Credibility bar with trusted data sources and statistics.
 */
export function CredibilityBar() {
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

interface StatItemProps {
  value: string;
  label: string;
}

/**
 * Stat item component for displaying statistics.
 */
export function StatItem({ value, label }: StatItemProps) {
  return (
    <div className="text-center">
      <p className="text-2xl md:text-3xl font-bold text-forest-300">{value}</p>
      <p className="text-xs text-forest-400/60 uppercase tracking-wider">
        {label}
      </p>
    </div>
  );
}
