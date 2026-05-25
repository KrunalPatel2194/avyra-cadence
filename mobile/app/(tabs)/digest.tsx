import {
  ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";
import Markdown from "react-native-markdown-display";

import { useDigestToday, useGenerateDigest } from "@/api/hooks";
import { colors, radii, spacing, type } from "@/theme";

export default function DigestScreen() {
  const { data, isLoading, isFetching, refetch } = useDigestToday();
  const gen = useGenerateDigest();

  if (isLoading) {
    return <View style={styles.empty}><ActivityIndicator color={colors.textMuted} /></View>;
  }

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg }}
      refreshControl={<RefreshControl refreshing={isFetching} onRefresh={refetch} tintColor={colors.textMuted} />}
    >
      {!data ? (
        <View style={styles.card}>
          <Text style={type.h2}>No digest yet</Text>
          <Text style={[type.muted, { marginTop: spacing.xs }]}>
            Your daily briefing arrives each morning at your set time. You can also generate one on demand.
          </Text>
          <Pressable
            onPress={() => gen.mutateAsync().then(() => refetch()).catch(() => {})}
            disabled={gen.isPending}
            style={[styles.btn, gen.isPending && { opacity: 0.6 }]}
          >
            <Text style={styles.btnLabel}>{gen.isPending ? "Generating…" : "Generate now"}</Text>
          </Pressable>
        </View>
      ) : (
        <View style={{ gap: spacing.lg }}>
          <Text style={type.h1}>{data.date}</Text>
          {data.highlights.length > 0 && (
            <View style={styles.card}>
              <Text style={type.tiny}>HIGHLIGHTS</Text>
              {data.highlights.map((h: string, i: number) => (
                <Text key={i} style={[type.body, { marginTop: spacing.xs }]}>• {h}</Text>
              ))}
            </View>
          )}
          <View style={styles.card}>
            <Markdown style={mdStyles}>{data.body_md}</Markdown>
          </View>
          <Text style={type.muted}>
            Generated at {new Date(data.generated_at).toLocaleString()}
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root:  { flex: 1, backgroundColor: colors.bg },
  empty: { flex: 1, alignItems: "center", justifyContent: "center" },
  card:  {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  btn:   { backgroundColor: colors.accent, padding: spacing.md, borderRadius: radii.md, alignItems: "center", marginTop: spacing.md },
  btnLabel: { color: colors.bg, fontWeight: "700" },
});

const mdStyles = {
  body:   { color: colors.text, fontSize: 15 },
  heading2: { color: colors.text, fontWeight: "700", fontSize: 18, marginTop: 12 },
  strong: { color: colors.text, fontWeight: "700" },
  bullet_list: { marginVertical: 6 },
  list_item: { color: colors.text },
  paragraph: { color: colors.text, marginVertical: 4 },
} as const;
