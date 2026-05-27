import { useRouter } from "expo-router";
import {
  ActivityIndicator, FlatList, StyleSheet, Text, View,
} from "react-native";

import { useEmails } from "@/api/hooks";
import { EmailRow } from "@/components/EmailRow";
import { colors, spacing, type } from "@/theme";

export default function InboxScreen() {
  const router = useRouter();
  const { data, isLoading } = useEmails();

  if (isLoading) {
    return <View style={styles.empty}><ActivityIndicator color={colors.textMuted} /></View>;
  }

  const items = data?.items ?? [];

  return (
    <FlatList
      style={styles.root}
      data={items}
      keyExtractor={(e) => e.id}
      renderItem={({ item }) => (
        <EmailRow item={item} onPress={() => router.push(`/email/${item.id}`)} />
      )}
      ListEmptyComponent={
        <View style={styles.empty}>
          <Text style={type.muted}>
            No emails yet. Cadence checks your inbox every 4 hours — your first
            batch arrives shortly after sign-in.
          </Text>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  empty: { padding: spacing.xl, alignItems: "center", justifyContent: "center" },
});
