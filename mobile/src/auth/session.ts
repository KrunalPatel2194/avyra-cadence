// Lightweight session store — `signedIn` is the only thing screens really need
// to branch on. After /auth/google/exchange we save the JWT and flip this.
import { create } from "zustand";

import { api, clearJwt, saveJwt } from "@/api/client";
import type { ExchangeResponse, User } from "@/api/types";
import * as SecureStore from "expo-secure-store";

const USER_KEY = "cadence.user";

type SessionState = {
  signedIn: boolean | null;       // null = unknown (still bootstrapping)
  user: User | null;
  hydrate: () => Promise<void>;
  exchange: (args: { code: string; codeVerifier: string; redirectUri: string; tz?: string }) => Promise<void>;
  devLogin: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  setUser: (u: User) => void;
};

export const useSession = create<SessionState>((set, get) => ({
  signedIn: null,
  user: null,

  hydrate: async () => {
    const jwt = await SecureStore.getItemAsync("cadence.jwt");
    if (!jwt) {
      set({ signedIn: false, user: null });
      return;
    }
    // We have a token — try to load `me`. If it 401s, we drop it.
    try {
      const me = await api.get<User>("/auth/me");
      set({ signedIn: true, user: me });
      await SecureStore.setItemAsync(USER_KEY, JSON.stringify(me));
    } catch {
      await clearJwt();
      set({ signedIn: false, user: null });
    }
  },

  exchange: async ({ code, codeVerifier, redirectUri, tz }) => {
    const resp = await api.post<ExchangeResponse>("/auth/google/exchange", {
      code, code_verifier: codeVerifier, redirect_uri: redirectUri, tz,
    }, { auth: false });
    await saveJwt(resp.jwt);
    await SecureStore.setItemAsync(USER_KEY, JSON.stringify(resp.user));
    set({ signedIn: true, user: resp.user });
  },

  devLogin: async (email: string) => {
    const tz = Intl?.DateTimeFormat?.()?.resolvedOptions?.()?.timeZone;
    const resp = await api.post<ExchangeResponse>("/auth/dev-login", { email, tz }, { auth: false });
    await saveJwt(resp.jwt);
    await SecureStore.setItemAsync(USER_KEY, JSON.stringify(resp.user));
    set({ signedIn: true, user: resp.user });
  },

  signOut: async () => {
    try { await api.post("/auth/revoke"); } catch { /* best-effort */ }
    await clearJwt();
    await SecureStore.deleteItemAsync(USER_KEY);
    set({ signedIn: false, user: null });
  },

  setUser: (u) => set({ user: u }),
}));
