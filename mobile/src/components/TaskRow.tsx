import { Pressable, StyleSheet, Text, View } from "react-native";

import type { TaskOut } from "@/api/types";
import { colors, radii, spacing, type } from "@/theme";

const PRIORITY_COLOR: Record<TaskOut["priority"], string> = {
  high: colors.urgent,
  med:  colors.warn,
  low:  colors.textMuted,
};

const SOURCE_LABEL: Record<TaskOut["source_type"], string> = {
  email:  "EMAIL",
  manual: "ME",
  news:   "NEWS",
};

export function TaskRow({
  task,
  onToggle,
  onPress,
}: {
  task: TaskOut;
  onToggle: () => void;
  onPress?: () => void;
}) {
  const isDone = task.status === "done";
  const isSnoozed = task.status === "snoozed";

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && { opacity: 0.85 }]}>
      <Pressable onPress={onToggle} hitSlop={12} style={[styles.check, isDone && styles.checkDone]}>
        {isDone && <Text style={styles.checkMark}>✓</Text>}
      </Pressable>
      <View style={{ flex: 1 }}>
        <Text style={[styles.title, isDone && styles.titleDone]} numberOfLines={2}>
          {task.title}
        </Text>
        <View style={styles.meta}>
          <View style={[styles.dot, { backgroundColor: PRIORITY_COLOR[task.priority] }]} />
          <Text style={styles.metaText}>{SOURCE_LABEL[task.source_type]}</Text>
          {task.due_date && (
            <Text style={styles.metaText}>· due {task.due_date}{task.due_time ? ` ${task.due_time.slice(0,5)}` : ""}</Text>
          )}
          {isSnoozed && <Text style={[styles.metaText, { color: colors.warn }]}>· suggested</Text>}
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  check: {
    width: 22, height: 22,
    borderRadius: radii.sm,
    borderWidth: 1.5,
    borderColor: colors.textMuted,
    alignItems: "center", justifyContent: "center",
    marginTop: 2,
  },
  checkDone: { backgroundColor: colors.success, borderColor: colors.success },
  checkMark: { color: colors.bg, fontSize: 13, fontWeight: "700" },
  title: { ...type.body },
  titleDone: { color: colors.textMuted, textDecorationLine: "line-through" },
  meta: { flexDirection: "row", alignItems: "center", marginTop: 4, gap: spacing.xs },
  dot: { width: 6, height: 6, borderRadius: 3 },
  metaText: { ...type.muted },
});
