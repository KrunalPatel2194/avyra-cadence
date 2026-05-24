import { useRouter } from "expo-router";
import { useState } from "react";
import {
  Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import { useCreateTask } from "@/api/hooks";
import type { TaskPriority } from "@/api/types";
import { colors, radii, spacing, type } from "@/theme";

const PRIORITIES: TaskPriority[] = ["low", "med", "high"];

export default function NewTask() {
  const router = useRouter();
  const create = useCreateTask();
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [dueDate, setDueDate] = useState("");        // YYYY-MM-DD
  const [dueTime, setDueTime] = useState("");        // HH:MM
  const [priority, setPriority] = useState<TaskPriority>("low");

  const submit = async () => {
    if (!title.trim()) {
      Alert.alert("Add a title");
      return;
    }
    try {
      await create.mutateAsync({
        title: title.trim(),
        notes: notes.trim() || undefined,
        due_date: dueDate.trim() || undefined,
        due_time: dueTime.trim() ? `${dueTime.trim()}:00` : undefined,
        priority,
      });
      router.back();
    } catch (e: unknown) {
      const detail = (e as { detail?: string })?.detail || "create failed";
      Alert.alert("Couldn't save", detail);
    }
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg }}>
      <View>
        <Text style={styles.label}>Title</Text>
        <TextInput
          value={title}
          onChangeText={setTitle}
          placeholder="What needs to happen?"
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          autoFocus
        />
      </View>

      <View>
        <Text style={styles.label}>Notes (optional)</Text>
        <TextInput
          value={notes}
          onChangeText={setNotes}
          placeholder="Context, links, who"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, { minHeight: 80, textAlignVertical: "top" }]}
          multiline
        />
      </View>

      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>Due date</Text>
          <TextInput
            value={dueDate}
            onChangeText={setDueDate}
            placeholder="2026-05-25"
            placeholderTextColor={colors.textMuted}
            style={styles.input}
            autoCapitalize="none"
          />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>Time</Text>
          <TextInput
            value={dueTime}
            onChangeText={setDueTime}
            placeholder="17:00"
            placeholderTextColor={colors.textMuted}
            style={styles.input}
            autoCapitalize="none"
          />
        </View>
      </View>

      <View>
        <Text style={styles.label}>Priority</Text>
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          {PRIORITIES.map((p) => (
            <Pressable
              key={p}
              onPress={() => setPriority(p)}
              style={[styles.chip, priority === p && styles.chipActive]}
            >
              <Text style={[styles.chipLabel, priority === p && styles.chipLabelActive]}>{p}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <Pressable onPress={submit} disabled={create.isPending} style={[styles.submit, create.isPending && { opacity: 0.6 }]}>
        <Text style={styles.submitLabel}>{create.isPending ? "Saving…" : "Add task"}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  label: { ...type.tiny, marginBottom: spacing.xs },
  row: { flexDirection: "row", gap: spacing.md },
  input: {
    backgroundColor: colors.surface,
    color: colors.text,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 15,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chip: { paddingVertical: 6, paddingHorizontal: spacing.lg, borderRadius: radii.pill, backgroundColor: colors.surfaceAlt },
  chipActive: { backgroundColor: colors.accent },
  chipLabel: { ...type.muted, color: colors.textMuted, textTransform: "capitalize" },
  chipLabelActive: { color: colors.bg, fontWeight: "600" },
  submit: {
    backgroundColor: colors.text,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    alignItems: "center",
    marginTop: spacing.md,
  },
  submitLabel: { color: colors.bg, fontWeight: "700", fontSize: 16 },
});
