// Sign-in screen — single Google button. Handles the PKCE response and posts
// the auth code to cadence-api for token exchange.
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { useGoogleAuthRequest } from "@/auth/google";
import { useSession } from "@/auth/session";
import { colors, radii, spacing, type } from "@/theme";

export default function SignIn() {
  const { request, response, promptAsync, redirectUri } = useGoogleAuthRequest();
  const { exchange } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (response?.type !== "success") return;
    const code = response.params.code;
    // expo-auth-session attaches the PKCE verifier to request.codeVerifier
    const codeVerifier = (request as unknown as { codeVerifier?: string } | null)?.codeVerifier;
    if (!code || !codeVerifier) {
      setError("Sign-in did not return an auth code.");
      return;
    }
    setBusy(true);
    setError(null);
    const tz = Intl?.DateTimeFormat()?.resolvedOptions()?.timeZone;
    exchange({ code, codeVerifier, redirectUri, tz })
      .catch((e: { detail?: string }) => setError(e?.detail || "exchange failed"))
      .finally(() => setBusy(false));
  }, [response, request, redirectUri, exchange]);

  return (
    <View style={styles.root}>
      <View style={styles.center}>
        <Text style={[type.h1, styles.title]}>Cadence</Text>
        <Text style={[type.muted, styles.subtitle]}>
          Your inbox, summarized. Your day, on track.
        </Text>

        <Pressable
          onPress={() => { setError(null); promptAsync(); }}
          disabled={!request || busy}
          style={({ pressed }) => [
            styles.btn,
            (!request || busy) && styles.btnDisabled,
            pressed && { opacity: 0.85 },
          ]}
        >
          {busy ? <ActivityIndicator color="#0B0B0F" /> : (
            <Text style={styles.btnLabel}>Continue with Google</Text>
          )}
        </Pressable>

        {error && <Text style={styles.error}>{error}</Text>}

        <Text style={[type.muted, styles.fine]}>
          We only request read-only Gmail access. Your messages never leave your in-house LLM.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg, padding: spacing.xl, justifyContent: "center" },
  center: { gap: spacing.lg },
  title: { textAlign: "center" },
  subtitle: { textAlign: "center", marginBottom: spacing.xl },
  btn: {
    backgroundColor: colors.text,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    alignItems: "center",
  },
  btnDisabled: { opacity: 0.5 },
  btnLabel: { color: colors.bg, fontWeight: "600", fontSize: 16 },
  error: { color: colors.urgent, textAlign: "center", marginTop: spacing.sm },
  fine: { textAlign: "center", marginTop: spacing.xl },
});
