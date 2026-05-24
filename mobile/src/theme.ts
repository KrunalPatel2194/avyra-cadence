// Single source of palette/spacing/typography. Dark-first, kept restrained.
export const colors = {
  bg: "#0B0B0F",
  surface: "#15151B",
  surfaceAlt: "#1E1E26",
  border: "#2A2A35",
  text: "#F2F2F4",
  textMuted: "#9899A5",
  accent: "#7AA2FF",
  urgent: "#FF7A7A",
  success: "#74D69C",
  warn: "#F0B85B",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
export const radii  = { sm: 6, md: 10, lg: 14, pill: 999 };

export const type = {
  h1:   { fontSize: 26, fontWeight: "700" as const, color: colors.text },
  h2:   { fontSize: 20, fontWeight: "600" as const, color: colors.text },
  body: { fontSize: 15, fontWeight: "400" as const, color: colors.text },
  muted:{ fontSize: 13, fontWeight: "400" as const, color: colors.textMuted },
  tiny: { fontSize: 11, fontWeight: "500" as const, color: colors.textMuted, textTransform: "uppercase" as const, letterSpacing: 0.5 },
};
