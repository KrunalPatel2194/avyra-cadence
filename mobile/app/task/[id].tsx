// Task detail — full info on one task, with mark-done / snooze / delete.
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";

import { api } from "@/api/client";
import { useDeleteTask, useUpdateTask } from "@/api/hooks";
import type { TaskOut } from "@/api/types";
import { colors, radii, spacing, type } from "@/theme";
import { useQuery } from "@tanstack/react-query";

function fetchTask(id: string) {
  // Tasks list endpoint returns all of them; for a single detail we filter
  // client-side. Avoids adding a new backend route just for this.
  return api.get<TaskOut[]>(`/tasks?status=open&due=all&source=all&limit=500`).then(
    (rows) => rows.find((t) => t.id === id),
  );
}

const PRIORITY_COLOR: Record<TaskOut["priority"], string> = {
  high: colors.urgent,
  med:  colors.warn,
  low:  colors.textMuted,
};

const SOURCE_LABEL: Record<TaskOut["source_type"], string> = {
  email:  "From an email",
  manual: "You added this",
  news:   "From a news item",
};

function formatTime(due_time: string | null): string {
  if (!due_time) return "";
  // "HH:MM:SS" → "HH:MM"
  return due_time.slice(0, 5);
}

export default function TaskDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const update = useUpdateTask();
  const del = useDeleteTask();

  const { data: task, isLoading } = useQuery({
    queryKey: ["task", id],
    queryFn: () => fetchTask(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return <View style={styles.empty}><ActivityIndicator color={colors.textMuted} /></View>;
  }
  if (!task) {
    return (
      <View style={styles.empty}>
        <Text style={type.muted}>Task not found.</Text>
      </View>
    );
  }

  const onToggleDone = async () => {
    await update.mutateAsync({
      id: task.id,
      patch: { status: task.status === "done" ? "open" : "done" },
    });
    router.back();
  };

  const onSnooze = async () => {
    await update.mutateAsync({ id: task.id, patch: { status: "snoozed" } });
    router.back();
  };

  const onDelete = () => {
    Alert.alert("Delete task?", "This can't be undone.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          await del.mutateAsync(task.id);
          router.back();
        },
      },
    ]);
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg }}>
      {/* Title + source */}
      <View>
        <Text style={[type.tiny, { color: PRIORITY_COLOR[task.priority] }]}>{task.priority.toUpperCase()} PRIORITY</Text>
        <Text style={[styles.title]}>{task.title}</Text>
        <Text style={[type.muted, { marginTop: 6 }]}>{SOURCE_LABEL[task.source_type]}</Text>
      </View>

      {/* When */}
      {(task.due_date || task.due_time || task.remind_at) && (
        <View style={styles.card}>
          <Text style={type.tiny}>WHEN</Text>
          {task.due_date && (
            <Text style={[type.body, { marginTop: spacing.xs }]}>
              Due {task.due_date}{task.due_time ? ` at ${formatTime(task.due_time)}` : ""}
            </Text>
          )}
          {task.remind_at && (
            <Text style={type.muted}>Remind me at {new Date(task.remind_at).toLocaleString()}</Text>
          )}
          {!task.due_date && !task.remind_at && (
            <Text style={type.muted}>No date set</Text>
          )}
        </View>
      )}

      {/* Notes (manual) or Rationale (LLM) */}
      {task.notes ? (
        <View style={styles.card}>
          <Text style={type.tiny}>NOTES</Text>
          <Text style={[type.body, { marginTop: spacing.xs }]}>{task.notes}</Text>
        </View>
      ) : null}

      {task.rationale ? (
        <View style={styles.card}>
          <Text style={type.tiny}>WHY THIS WAS PICKED UP</Text>
          <Text style={[type.body, { marginTop: spacing.xs, fontStyle: "italic" }]}>
            “{task.rationale}”
          </Text>
          {task.confidence !== null && (
            <Text style={[type.muted, { marginTop: spacing.xs }]}>
              Confidence: {(task.confidence * 100).toFixed(0)}%
            </Text>
          )}
        </View>
      ) : null}

      {task.source_type === "email" && task.source_ref && (
        <Pressable
          onPress={() => router.push(`/email/${task.source_ref}`)}
          style={({ pressed }) => [styles.cardLink, pressed && { opacity: 0.85 }]}
        >
          <Text style={[type.body, { color: colors.accent }]}>Open the source email →</Text>
        </Pressable>
      )}

      {/* Actions */}
      <View style={{ gap: spacing.sm, marginTop: spacing.lg }}>
        <Pressable onPress={onToggleDone} style={styles.primaryBtn}>
          <Text style={styles.primaryBtnLabel}>
            {task.status === "done" ? "Reopen" : "Mark done"}
          </Text>
        </Pressable>

        {task.status !== "snoozed" && (
          <Pressable onPress={onSnooze} style={styles.secondaryBtn}>
            <Text style={styles.secondaryBtnLabel}>Snooze (move to suggested)</Text>
          </Pressable>
        )}

        <Pressable onPress={onDelete} style={styles.dangerBtn}>
          <Text style={styles.dangerBtnLabel}>Delete</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },

  title: {
    color: colors.text,
    fontSize: 24,
    fontWeight: "700",
    letterSpacing: -0.4,
    marginTop: spacing.xs,
  },

  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardLink: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },

  primaryBtn: {
    backgroundColor: colors.text,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    alignItems: "center",
  },
  primaryBtnLabel: { color: colors.bg, fontWeight: "700", fontSize: 16 },

  secondaryBtn: {
    backgroundColor: colors.surfaceAlt,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    alignItems: "center",
  },
  secondaryBtnLabel: { color: colors.text, fontWeight: "600", fontSize: 15 },

  dangerBtn: {
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    alignItems: "center",
  },
  dangerBtnLabel: { color: colors.urgent, fontWeight: "600", fontSize: 14 },
});
