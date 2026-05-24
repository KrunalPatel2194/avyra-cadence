import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useMe } from "@/api/hooks";
import { useSession } from "@/auth/session";
import { colors, radii, spacing, type } from "@/theme";

export default function SettingsScreen() {
  const { data: me } = useMe();
  const { signOut } = useSession();

  const confirmSignOut = () => {
    Alert.alert("Sign out?", "You'll need to sign back in to use Cadence.", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign out", style: "destructive", onPress: () => signOut() },
    ]);
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ padding: spacing.lg, gap: spacing.lg }}>
      <View style={styles.card}>
        <Text style={type.tiny}>ACCOUNT</Text>
        <Text style={[type.body, { marginTop: spacing.sm }]}>{me?.name || "—"}</Text>
        <Text style={type.muted}>{me?.email}</Text>
        <Text style={[type.muted, { marginTop: spacing.xs }]}>
          Gmail: {me?.gmail_linked ? "linked" : "not linked"}
        </Text>
        <Text style={type.muted}>Timezone: {me?.tz}</Text>
      </View>

      <View style={styles.card}>
        <Text style={type.tiny}>SCHEDULE</Text>
        <Text style={[type.body, { marginTop: spacing.sm }]}>Gmail check: every 2 hours</Text>
        <Text style={type.muted}>
          Cadence polls your inbox every 2 hours. Pull to refresh on Inbox or Tasks for an on-demand check.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={type.tiny}>LLM</Text>
        <Text style={[type.body, { marginTop: spacing.sm }]}>In-house (Ollama via ai-engine)</Text>
        <Text style={type.muted}>
          Email content is processed by your own LLM. No third-party AI provider.
        </Text>
      </View>

      <Pressable onPress={confirmSignOut} style={styles.signOut}>
        <Text style={styles.signOutLabel}>Sign out</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root:  { flex: 1, backgroundColor: colors.bg },
  card:  { backgroundColor: colors.surface, borderRadius: radii.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border },
  signOut: { backgroundColor: colors.surfaceAlt, padding: spacing.md, borderRadius: radii.md, alignItems: "center" },
  signOutLabel: { color: colors.urgent, fontWeight: "600" },
});
