import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View,
} from "react-native";

import { useTasks, useUpdateTask } from "@/api/hooks";
import { TaskRow } from "@/components/TaskRow";
import { colors, radii, spacing, type } from "@/theme";

type Filter = "today" | "week" | "overdue" | "all";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "today",   label: "Today" },
  { key: "week",    label: "This week" },
  { key: "overdue", label: "Overdue" },
  { key: "all",     label: "All" },
];

export default function TasksScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("today");
  const { data, isLoading, isFetching, refetch } = useTasks("open", filter, "all");
  const update = useUpdateTask();

  const rows = useMemo(() => data ?? [], [data]);

  return (
    <View style={styles.root}>
      <View style={styles.filterRow}>
        {FILTERS.map((f) => (
          <Pressable
            key={f.key}
            onPress={() => setFilter(f.key)}
            style={[styles.chip, filter === f.key && styles.chipActive]}
          >
            <Text style={[styles.chipLabel, filter === f.key && styles.chipLabelActive]}>{f.label}</Text>
          </Pressable>
        ))}
      </View>

      {isLoading ? (
        <View style={styles.empty}>
          <ActivityIndicator color={colors.textMuted} />
        </View>
      ) : rows.length === 0 ? (
        <View style={styles.empty}>
          <Text style={type.muted}>No open tasks here.</Text>
        </View>
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(t) => t.id}
          renderItem={({ item }) => (
            <TaskRow
              task={item}
              onToggle={() => update.mutate({ id: item.id, patch: { status: item.status === "done" ? "open" : "done" } })}
            />
          )}
          refreshControl={
            <RefreshControl refreshing={isFetching} onRefresh={refetch} tintColor={colors.textMuted} />
          }
        />
      )}

      <Pressable onPress={() => router.push("/task/new")} style={styles.fab}>
        <Text style={styles.fabPlus}>+</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  filterRow: {
    flexDirection: "row", gap: spacing.xs,
    padding: spacing.md,
    backgroundColor: colors.bg,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  chip: {
    paddingVertical: 6, paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: colors.surfaceAlt,
  },
  chipActive: { backgroundColor: colors.text },
  chipLabel: { ...type.muted, color: colors.textMuted },
  chipLabelActive: { color: colors.bg, fontWeight: "600" },
  empty: { flex: 1, alignItems: "center", justifyContent: "center" },
  fab: {
    position: "absolute", right: spacing.xl, bottom: spacing.xl,
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: colors.accent,
    alignItems: "center", justifyContent: "center",
    shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 10, shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  fabPlus: { color: colors.bg, fontSize: 28, lineHeight: 30, fontWeight: "700" },
});
