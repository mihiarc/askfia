"use client";

interface FeaturePillProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

/**
 * Feature pill component for displaying feature highlights.
 */
export function FeaturePill({ icon: Icon, label }: FeaturePillProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-forest-900/50 backdrop-blur-sm border border-forest-700/30 text-forest-200 text-sm transition-all duration-300 hover:bg-forest-800/50 hover:border-forest-600/40">
      <Icon className="h-4 w-4 text-forest-400" />
      <span>{label}</span>
    </div>
  );
}
