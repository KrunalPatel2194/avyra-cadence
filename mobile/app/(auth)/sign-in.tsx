// Sign-in screen — modern dark hero, single Google CTA, soft animated entry.
// No native modules required: the "gradient" is faked with stacked translucent
// View layers, which lets us avoid a prebuild round-trip just for the BG.
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Animated, Easing, Pressable, StyleSheet, Text, View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { isCancelled } from "@/auth/google";
import { useSession } from "@/auth/session";
import { colors, radii, spacing } from "@/theme";

export default function SignIn() {
  const { signInWithGoogle } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Entry animation: fade + lift logo, then content settles in.
  const fade = useRef(new Animated.Value(0)).current;
  const lift = useRef(new Animated.Value(24)).current;
  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, { toValue: 1, duration: 520, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
      Animated.timing(lift, { toValue: 0, duration: 520, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
    ]).start();
  }, [fade, lift]);

  const onSignInPress = async () => {
    setError(null);
    setBusy(true);
    try {
      await signInWithGoogle();
    } catch (e: unknown) {
      if (isCancelled(e)) {
        // User dismissed the modal — silent.
        return;
      }
      const msg = (e as { detail?: string; message?: string })?.detail
        || (e as { message?: string })?.message
        || "sign-in failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const animStyle = { opacity: fade, transform: [{ translateY: lift }] };

  return (
    <View style={styles.root}>
      {/* Faked gradient — three stacked layers blend into the bg color */}
      <View style={[styles.bgLayer, { backgroundColor: "#15151B", opacity: 1 }]} />
      <View style={[styles.bgLayer, { backgroundColor: "#0B0B0F", opacity: 0.85, top: "30%" }]} />
      <View style={[styles.bgLayer, { backgroundColor: "#000000", opacity: 0.75, top: "60%" }]} />
      {/* Soft accent glow at the top */}
      <View style={styles.glow} pointerEvents="none" />

      <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
        {/* Brand */}
        <Animated.View style={[styles.brand, animStyle]}>
          <View style={styles.mark}>
            <Text style={styles.markGlyph}>C</Text>
          </View>
          <Text style={styles.wordmark}>Cadence</Text>
          <Text style={styles.tagline}>Your inbox, summarized.{"\n"}Your day, on track.</Text>
        </Animated.View>

        {/* CTA */}
        <Animated.View style={[styles.cta, animStyle]}>
          <Pressable
            onPress={onSignInPress}
            disabled={busy}
            style={({ pressed }) => [
              styles.btn,
              busy && styles.btnDisabled,
              pressed && styles.btnPressed,
            ]}
          >
            {busy ? (
              <ActivityIndicator color="#0B0B0F" />
            ) : (
              <View style={styles.btnInner}>
                <GoogleGlyph />
                <Text style={styles.btnLabel}>Continue with Google</Text>
              </View>
            )}
          </Pressable>

          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          <Text style={styles.fine}>
            Read-only Gmail access. All summarization runs on your in-house LLM —
            no third-party AI provider.
          </Text>
        </Animated.View>
      </SafeAreaView>
    </View>
  );
}

// Tiny inline Google "G" mark — avoids a remote image / extra dep.
function GoogleGlyph() {
  return (
    <View style={styles.gWrap}>
      <Text style={styles.gLetter}>G</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },

  // Background layers
  bgLayer: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0 },
  glow: {
    position: "absolute",
    top: -200, left: -120, right: -120,
    height: 460,
    borderRadius: 240,
    backgroundColor: colors.accent,
    opacity: 0.10,
    transform: [{ scaleX: 1.4 }],
  },

  safe: { flex: 1, paddingHorizontal: spacing.xl, justifyContent: "space-between" },

  brand: { marginTop: spacing.xxl + 24, alignItems: "flex-start", gap: spacing.lg },
  mark: {
    width: 56, height: 56,
    borderRadius: 16,
    backgroundColor: "rgba(255,255,255,0.06)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
    alignItems: "center", justifyContent: "center",
  },
  markGlyph: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "700",
    letterSpacing: -1,
    marginTop: -2,
  },
  wordmark: {
    color: colors.text,
    fontSize: 44,
    fontWeight: "800",
    letterSpacing: -1.4,
    marginTop: spacing.sm,
  },
  tagline: {
    color: colors.textMuted,
    fontSize: 16,
    lineHeight: 22,
    maxWidth: 320,
  },

  cta: { marginBottom: spacing.xl + 8, gap: spacing.lg },
  btn: {
    backgroundColor: colors.text,
    borderRadius: radii.lg,
    paddingVertical: 16,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.45,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
  },
  btnDisabled: { opacity: 0.45 },
  btnPressed: { transform: [{ scale: 0.985 }], opacity: 0.92 },
  btnInner: { flexDirection: "row", alignItems: "center", gap: 10 },
  btnLabel: { color: colors.bg, fontSize: 16, fontWeight: "700", letterSpacing: -0.2 },

  gWrap: {
    width: 22, height: 22,
    borderRadius: 11,
    backgroundColor: colors.bg,
    alignItems: "center", justifyContent: "center",
  },
  gLetter: { color: colors.text, fontSize: 14, fontWeight: "800", marginTop: -1 },

  errorBox: {
    backgroundColor: "rgba(255,122,122,0.08)",
    borderColor: "rgba(255,122,122,0.35)",
    borderWidth: 1,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  errorText: { color: colors.urgent, fontSize: 13 },

  fine: {
    color: colors.textMuted,
    fontSize: 12,
    lineHeight: 18,
    textAlign: "center",
    paddingHorizontal: spacing.sm,
  },

  devBtn: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: "#222",
    borderRadius: radii.md,
  },
  devBtnText: {
    color: "#999",
    fontSize: 12,
    textAlign: "center",
  },
});