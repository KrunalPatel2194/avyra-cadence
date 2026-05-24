// Default landing — AuthGate redirects to /(auth)/sign-in or /(tabs)/tasks
// depending on session state. Render a quiet stub here so the splash sees
// something before the redirect fires.
import { ActivityIndicator, View } from "react-native";

import { colors } from "@/theme";

export default function Index() {
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
      <ActivityIndicator color={colors.textMuted} />
    </View>
  );
}
