// Root layout — bootstraps session + React Query + push registration.
// Uses expo-router file-based routing.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { useSession } from "@/auth/session";
import { registerForPush } from "@/push/register";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

function AuthGate({ children }: { children: React.ReactNode }) {
  const { signedIn, hydrate } = useSession();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => { hydrate(); }, [hydrate]);

  useEffect(() => {
    if (signedIn === null) return;
    const inAuthGroup = segments[0] === "(auth)";
    if (!signedIn && !inAuthGroup) {
      router.replace("/(auth)/sign-in");
    } else if (signedIn && inAuthGroup) {
      router.replace("/(tabs)/tasks");
    }
  }, [signedIn, segments, router]);

  useEffect(() => {
    if (signedIn) {
      // Best-effort — silently no-ops on simulator / Expo Go.
      registerForPush().catch(() => {});
    }
  }, [signedIn]);

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <AuthGate>
            <StatusBar style="light" />
            <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "#0B0B0F" } }}>
              <Stack.Screen name="(auth)" />
              <Stack.Screen name="(tabs)" />
              <Stack.Screen name="email/[id]" options={{ headerShown: true, headerTitle: "Email", headerStyle: { backgroundColor: "#0B0B0F" }, headerTintColor: "#F2F2F4" }} />
              <Stack.Screen name="task/new"   options={{ presentation: "modal", headerShown: true, headerTitle: "New task", headerStyle: { backgroundColor: "#0B0B0F" }, headerTintColor: "#F2F2F4" }} />
            </Stack>
          </AuthGate>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
