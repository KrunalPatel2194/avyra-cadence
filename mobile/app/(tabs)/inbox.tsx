import { useRouter } from "expo-router";
import {
  ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, View,
} from "react-native";

import { useEmails, useRefreshEmails } from "@/api/hooks";
import { EmailRow } from "@/components/EmailRow";
import { colors, spacing, type } from "@/theme";

export default function InboxScreen() {
  const router = useRouter();
  const { data, isLoading, isFetching, refetch } = useEmails();
  const refresh = useRefreshEmails();

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
          <Text style={type.muted}>Nothing yet. Pull to refresh after Gmail finishes its first sync.</Text>
        </View>
      }
      refreshControl={
        <RefreshControl
          refreshing={isFetching || refresh.isPending}
          onRefresh={async () => { await refresh.mutateAsync().catch(() => {}); await refetch(); }}
          tintColor={colors.textMuted}
        />
      }
    />
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  empty: { padding: spacing.xl, alignItems: "center", justifyContent: "center" },
});
