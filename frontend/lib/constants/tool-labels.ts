/**
 * Human-readable labels for FIA query tools.
 *
 * These labels are displayed in the chat interface when tool calls
 * are shown to the user.
 */

export const TOOL_LABELS: Record<string, string> = {
  // FIA Survey Tools (from agent.py)
  query_forest_area: "Forest Area",
  query_timber_volume: "Timber Volume",
  query_biomass_carbon: "Biomass & Carbon",
  query_trees_per_acre: "Trees Per Acre",
  query_tpa: "Trees Per Acre",
  query_mortality: "Mortality",
  query_removals: "Harvest Removals",
  query_growth: "Growth",
  query_area_change: "Area Change",
  query_by_forest_type: "By Forest Type",
  query_by_stand_size: "By Stand Size",
  query_by_ownership: "By Ownership",
  query_by_county: "By County",
  compare_states: "State Comparison",
  lookup_species: "Species Lookup",
  lookup_forest_type: "Forest Type Lookup",

  // GridFIA Spatial Tools (from gridfia_tools.py)
  query_gridfia_species_list: "Species List (Spatial)",
  query_species_diversity: "Species Diversity (Spatial)",
  query_gridfia_biomass: "Biomass (Spatial)",
  query_dominant_species: "Dominant Species (Spatial)",
  compare_gridfia_locations: "Location Comparison (Spatial)",
  query_species_specific_biomass: "Species Biomass (Spatial)",
};

/**
 * Get a human-readable label for a tool name.
 *
 * @param toolName - The tool name from the API
 * @returns Human-readable label, or the original name if not found
 */
export function getToolLabel(toolName: string): string {
  return TOOL_LABELS[toolName] || toolName;
}
