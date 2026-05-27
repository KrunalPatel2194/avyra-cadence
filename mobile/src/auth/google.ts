// Native Google Sign-In via @react-native-google-signin/google-signin.
//
// Why this over expo-auth-session:
//   - In-app modal (uses Google's native iOS SDK), no Safari redirect.
//   - No reverse-DNS/PKCE URI quirks — the SDK handles everything.
//   - Returns serverAuthCode that the backend exchanges for refresh_token.
//
// Requires a NATIVE BUILD (npx expo run:ios). Does NOT work in Expo Go —
// the iOS native module isn't bundled there.
import {
  GoogleSignin,
  isErrorWithCode,
  statusCodes,
} from "@react-native-google-signin/google-signin";

import { config } from "@/config";

const GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly";

let configured = false;

function ensureConfigured() {
  if (configured) return;
  if (!config.googleIosClientId || !config.googleWebClientId) {
    throw new Error("googleIosClientId and googleWebClientId must both be set in config.ts");
  }
  GoogleSignin.configure({
    iosClientId: config.googleIosClientId,
    // webClientId is what authorises serverAuthCode for the backend exchange.
    // Without it, signIn returns no serverAuthCode and we can't get a refresh_token.
    webClientId: config.googleWebClientId,
    offlineAccess: true,                    // → returns serverAuthCode
    scopes: ["openid", "email", "profile", GMAIL_SCOPE],
    forceCodeForRefreshToken: true,         // ensures fresh refresh_token on every sign-in
  });
  configured = true;
}

export type NativeGoogleResult = {
  serverAuthCode: string;
  idToken: string;
  email: string;
  name: string;
};

export async function signInWithGoogleNative(): Promise<NativeGoogleResult> {
  ensureConfigured();
  await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: false });
  const result = await GoogleSignin.signIn();

  // Library v13+ returns { type, data }. Older returns the data directly.
  // Normalise.
  const data = (result as { type?: string; data?: unknown }).data ?? result;
  const d = data as {
    serverAuthCode?: string | null;
    idToken?: string | null;
    user?: { email?: string; name?: string };
  };

  if (!d.serverAuthCode) {
    throw new Error("Google sign-in did not return a serverAuthCode — check Web client config");
  }
  return {
    serverAuthCode: d.serverAuthCode,
    idToken: d.idToken || "",
    email: d.user?.email || "",
    name: d.user?.name || "",
  };
}

export function isCancelled(e: unknown): boolean {
  return isErrorWithCode(e) && e.code === statusCodes.SIGN_IN_CANCELLED;
}

export async function signOutGoogleNative(): Promise<void> {
  try { await GoogleSignin.signOut(); } catch { /* best-effort */ }
}
