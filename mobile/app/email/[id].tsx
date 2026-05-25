import { useLocalSearchParams } from "expo-router";
import {
  ActivityIndicator, ScrollView, StyleSheet, Text, View,
} from "react-native";

import { useEmail } from "@/api/hooks";
import { colors, radii, spacing, type } from "@/theme";

export default function EmailDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, isLoading } = useEmail(id);

  if (isLoading) {
    return <View style={styles.empty}><ActivityIndicator color={colors.textMuted} /></View>;
  }
  if (!data) {
    return <View style={styles.empty}><Text style={type.muted}>Email not found.</Text></View>;
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg }}>
      <View>
        <Text style={type.h2}>{data.subject || "(no subject)"}</Text>
        <Text style={[type.muted, { marginTop: 4 }]}>
          {data.from_addr || "(unknown)"} · {new Date(data.received_at).toLocaleString()}
        </Text>
      </View>

      {data.summary && (
        <View style={styles.card}>
          <Text style={type.tiny}>SUMMARY</Text>
          <Text style={[type.body, { marginTop: spacing.xs }]}>{data.summary}</Text>
          {data.is_urgent && <Text style={[type.tiny, { color: colors.urgent, marginTop: spacing.xs }]}>URGENT</Text>}
        </View>
      )}

      {data.tasks.length > 0 && (
        <View style={styles.card}>
          <Text style={type.tiny}>EXTRACTED TASKS</Text>
          {data.tasks.map((t: any) => (
            <View key={t.id} style={styles.task}>
              <Text style={type.body}>{t.title}</Text>
              {(t.due_date || t.priority) && (
                <Text style={type.muted}>
                  {t.due_date ? `due ${t.due_date}` : ""}
                  {t.due_date && t.priority ? " · " : ""}
                  {t.priority}
                </Text>
              )}
              {t.rationale && <Text style={[type.muted, { marginTop: 2, fontStyle: "italic" }]}>“{t.rationale}”</Text>}
            </View>
          ))}
        </View>
      )}

      <View style={styles.card}>
        <Text style={type.tiny}>FULL MESSAGE</Text>
        <Text style={[type.body, { marginTop: spacing.xs }]}>{data.body_text || "(empty body)"}</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root:  { flex: 1, backgroundColor: colors.bg },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, backgroundColor: colors.bg },
  card:  {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  task:  { paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
});
