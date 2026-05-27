// Tasks tab — the landing screen after sign-in.
//
// Layout: tasks grouped under date headers (Overdue → Today → Tomorrow →
// later dated days → No date). Within each section, ordered by due time
// (timed tasks first, then untimed), then by priority.
//
// Every row is clickable → /task/[id]. No pull-to-refresh exposed: the
// 4-hour scheduler is the only ingest path.
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View,
} from "react-native";

import { useTasks, useUpdateTask } from "@/api/hooks";
import type { TaskOut } from "@/api/types";
import { TaskRow } from "@/components/TaskRow";
import { colors, radii, spacing, type } from "@/theme";

type Scope = "today" | "week" | "overdue" | "all";

const SCOPES: { key: Scope; label: string }[] = [
  { key: "today",   label: "Today" },
  { key: "week",    label: "This week" },
  { key: "overdue", label: "Overdue" },
  { key: "all",     label: "All" },
];

type Section =
  | { kind: "header"; id: string; label: string; count: number }
  | { kind: "task"; id: string; task: TaskOut };

// Local helpers — keep date math simple and deterministic.
function isoDate(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function prettyDate(iso: string): string {
  const today = isoDate(new Date());
  const tomorrow = isoDate(new Date(Date.now() + 86_400_000));
  if (iso === today) return "Today";
  if (iso === tomorrow) return "Tomorrow";
  // "Mon, May 28"
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

const PRIORITY_RANK: Record<TaskOut["priority"], number> = { high: 0, med: 1, low: 2 };

function buildSections(tasks: TaskOut[]): Section[] {
  const today = isoDate(new Date());
  const overdue: TaskOut[] = [];
  const buckets: Record<string, TaskOut[]> = {};
  const undated: TaskOut[] = [];

  for (const t of tasks) {
    if (!t.due_date) {
      undated.push(t);
      continue;
    }
    if (t.due_date < today) {
      overdue.push(t);
    } else {
      (buckets[t.due_date] ??= []).push(t);
    }
  }

  // Sort each bucket: timed first (earlier time wins), then untimed.
  // Tie-break by priority then created_at.
  const sortBucket = (arr: TaskOut[]) => {
    arr.sort((a, b) => {
      const aHas = !!a.due_time, bHas = !!b.due_time;
      if (aHas !== bHas) return aHas ? -1 : 1;
      if (aHas && bHas && a.due_time !== b.due_time) {
        return (a.due_time || "").localeCompare(b.due_time || "");
      }
      const pa = PRIORITY_RANK[a.priority], pb = PRIORITY_RANK[b.priority];
      if (pa !== pb) return pa - pb;
      return a.created_at.localeCompare(b.created_at);
    });
  };
  sortBucket(overdue);
  Object.values(buckets).forEach(sortBucket);
  sortBucket(undated);

  const sections: Section[] = [];
  const push = (id: string, label: string, items: TaskOut[]) => {
    if (items.length === 0) return;
    sections.push({ kind: "header", id: `h-${id}`, label, count: items.length });
    for (const t of items) sections.push({ kind: "task", id: t.id, task: t });
  };

  push("overdue", "Overdue", overdue);
  const dates = Object.keys(buckets).sort();
  for (const d of dates) push(d, prettyDate(d), buckets[d]);
  push("undated", "No date", undated);

  return sections;
}

export default function TasksScreen() {
  const router = useRouter();
  const [scope, setScope] = useState<Scope>("today");
  const { data, isLoading } = useTasks("open", scope, "all");
  const update = useUpdateTask();

  const sections = useMemo(() => buildSections(data ?? []), [data]);

  return (
    <View style={styles.root}>
      <View style={styles.scopeRow}>
        {SCOPES.map((s) => (
          <Pressable
            key={s.key}
            onPress={() => setScope(s.key)}
            style={[styles.chip, scope === s.key && styles.chipActive]}
          >
            <Text style={[styles.chipLabel, scope === s.key && styles.chipLabelActive]}>{s.label}</Text>
          </Pressable>
        ))}
      </View>

      {isLoading ? (
        <View style={styles.empty}><ActivityIndicator color={colors.textMuted} /></View>
      ) : sections.length === 0 ? (
        <View style={styles.empty}>
          <Text style={type.h2}>You're clear.</Text>
          <Text style={[type.muted, { marginTop: spacing.xs, textAlign: "center" }]}>
            No open tasks for this view.{"\n"}New emails are scanned every 4 hours.
          </Text>
        </View>
      ) : (
        <FlatList
          data={sections}
          keyExtractor={(s) => s.id}
          renderItem={({ item }) =>
            item.kind === "header" ? (
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionLabel}>{item.label}</Text>
                <Text style={styles.sectionCount}>{item.count}</Text>
              </View>
            ) : (
              <TaskRow
                task={item.task}
                onPress={() => router.push(`/task/${item.task.id}`)}
                onToggle={() =>
                  update.mutate({
                    id: item.task.id,
                    patch: { status: item.task.status === "done" ? "open" : "done" },
                  })
                }
              />
            )
          }
          stickyHeaderIndices={
            sections.reduce<number[]>((acc, s, i) => {
              if (s.kind === "header") acc.push(i);
              return acc;
            }, [])
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scopeRow: {
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

  sectionHeader: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing.sm,
    backgroundColor: colors.bg,
  },
  sectionLabel: { ...type.tiny, color: colors.text, fontSize: 12, letterSpacing: 0.8 },
  sectionCount: {
    ...type.tiny, color: colors.textMuted,
    paddingHorizontal: spacing.sm, paddingVertical: 2,
    backgroundColor: colors.surfaceAlt, borderRadius: radii.pill,
    overflow: "hidden",
  },

  empty: {
    flex: 1, alignItems: "center", justifyContent: "center",
    padding: spacing.xl,
  },
});
