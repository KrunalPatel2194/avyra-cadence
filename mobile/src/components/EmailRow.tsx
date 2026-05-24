import { Pressable, StyleSheet, Text, View } from "react-native";

import type { EmailListItem } from "@/api/types";
import { colors, radii, spacing, type } from "@/theme";

function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export function EmailRow({ item, onPress }: { item: EmailListItem; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && { opacity: 0.85 }]}>
      <View style={styles.headerRow}>
        <Text style={styles.from} numberOfLines={1}>{item.from_addr || "(unknown)"}</Text>
        <Text style={styles.when}>{formatWhen(item.received_at)}</Text>
      </View>
      <Text style={styles.subject} numberOfLines={1}>{item.subject || "(no subject)"}</Text>
      <Text style={styles.summary} numberOfLines={2}>
        {item.summary || (item.processed ? "(no summary)" : "Summarizing…")}
      </Text>
      <View style={styles.badges}>
        {item.is_urgent && (
          <View style={[styles.badge, { backgroundColor: colors.urgent }]}><Text style={styles.badgeLabel}>URGENT</Text></View>
        )}
        {item.task_count > 0 && (
          <View style={[styles.badge, { backgroundColor: colors.accent }]}>
            <Text style={styles.badgeLabel}>{item.task_count} task{item.task_count === 1 ? "" : "s"}</Text>
          </View>
        )}
        {item.category && (
          <View style={[styles.badge, { backgroundColor: colors.surfaceAlt }]}>
            <Text style={[styles.badgeLabel, { color: colors.textMuted }]}>{item.category.toUpperCase()}</Text>
          </View>
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 4,
  },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  from:    { ...type.body, flex: 1, marginRight: spacing.sm, fontWeight: "600" },
  when:    { ...type.muted },
  subject: { ...type.body, color: colors.text, fontWeight: "500" },
  summary: { ...type.muted, marginTop: 2 },
  badges:  { flexDirection: "row", gap: spacing.xs, marginTop: spacing.xs },
  badge:   { paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: radii.pill },
  badgeLabel: { fontSize: 10, fontWeight: "700", color: colors.bg, letterSpacing: 0.5 },
});
