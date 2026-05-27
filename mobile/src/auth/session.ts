// Session store. Sign-in uses Google's native iOS SDK to get a serverAuthCode
// in-app (no browser redirect), then exchanges it with cadence-api for a JWT.
import { create } from "zustand";

import { api, clearJwt, saveJwt } from "@/api/client";
import { signInWithGoogleNative, signOutGoogleNative } from "@/auth/google";
import type { ExchangeResponse, User } from "@/api/types";
import * as SecureStore from "expo-secure-store";

const USER_KEY = "cadence.user";

type SessionState = {
  signedIn: boolean | null;       // null = unknown (still bootstrapping)
  user: User | null;
  hydrate: () => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  setUser: (u: User) => void;
};

export const useSession = create<SessionState>((set) => ({
  signedIn: null,
  user: null,

  hydrate: async () => {
    const jwt = await SecureStore.getItemAsync("cadence.jwt");
    if (!jwt) {
      set({ signedIn: false, user: null });
      return;
    }
    try {
      const me = await api.get<User>("/auth/me");
      set({ signedIn: true, user: me });
      await SecureStore.setItemAsync(USER_KEY, JSON.stringify(me));
    } catch {
      await clearJwt();
      set({ signedIn: false, user: null });
    }
  },

  signInWithGoogle: async () => {
    // 1) Native sign-in (in-app modal).
    const tz = Intl?.DateTimeFormat?.()?.resolvedOptions?.()?.timeZone;
    const native = await signInWithGoogleNative();
    // 2) Exchange the serverAuthCode for our JWT.
    const resp = await api.post<ExchangeResponse>(
      "/auth/google/native-exchange",
      { server_auth_code: native.serverAuthCode, tz },
      { auth: false },
    );
    await saveJwt(resp.jwt);
    await SecureStore.setItemAsync(USER_KEY, JSON.stringify(resp.user));
    set({ signedIn: true, user: resp.user });
  },

  signOut: async () => {
    try { await api.post("/auth/revoke"); } catch { /* best-effort */ }
    await signOutGoogleNative();
    await clearJwt();
    await SecureStore.deleteItemAsync(USER_KEY);
    set({ signedIn: false, user: null });
  },

  setUser: (u) => set({ user: u }),
}));
