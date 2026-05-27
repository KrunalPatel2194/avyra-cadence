// Google OAuth via expo-auth-session (PKCE). On success we send {code,
// codeVerifier, redirectUri} to cadence-api which performs the token exchange.
//
// IMPORTANT: do NOT override `redirectUri`. Google's iOS OAuth client only
// accepts the reverse-DNS of the client id (e.g. com.googleusercontent.apps.
// 123-abc:/oauthredirect). expo-auth-session's Google provider computes that
// automatically when you pass iosClientId — overriding with our custom
// `cadence://` scheme gets us a 400 `invalid_request` from Google.
//
// The reverse-DNS scheme MUST also be registered in iOS Info.plist as a
// CFBundleURLScheme — see app.json `ios.infoPlist.CFBundleURLTypes`.
import * as AuthSession from "expo-auth-session";
import * as Google from "expo-auth-session/providers/google";
import { useMemo } from "react";

import { config } from "@/config";

const GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly";

// Google's iOS OAuth client REQUIRES the redirect URI in this exact form:
//   com.googleusercontent.apps.<REVERSE_CLIENT_ID>:/oauthredirect
//             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^
//             scheme (registered in Info.plist)     SINGLE slash, then path
//
// Double slash (`://oauthredirect`) makes the URI parser treat `oauthredirect`
// as the authority/host instead of the path, which Google rejects as a
// redirect_uri mismatch — and Google packages that as `invalid_grant` in the
// token-endpoint response. So: single slash, no exceptions.
function buildIosRedirectUri(iosClientId: string): string {
  if (!iosClientId) return "";
  const reversedId = `com.googleusercontent.apps.${iosClientId.replace(".apps.googleusercontent.com", "")}`;
  // makeRedirectUri with `native` keeps the exact string we provide in dev builds.
  return AuthSession.makeRedirectUri({ native: `${reversedId}:/oauthredirect` });
}

export function useGoogleAuthRequest() {
  // Memoize so re-renders never produce a fresh URI (would force the
  // AuthRequest to re-init and generate a new PKCE verifier — making the
  // returned `code` and the stored verifier mismatch).
  const redirectUri = useMemo(() => buildIosRedirectUri(config.googleIosClientId), []);

  const [request, response, promptAsync] = Google.useAuthRequest({
    iosClientId: config.googleIosClientId || undefined,
    scopes: ["openid", "profile", "email", GMAIL_SCOPE],
    redirectUri,
    extraParams: {
      access_type: "offline",
      prompt: "consent",
    },
  });

  if (__DEV__) {
    // Logged once per hook init — useful only when chasing OAuth bugs.
    // Should show: built === request === non-empty, exactly equal.

    console.log("[google-oauth] redirectUri:", {
      built: redirectUri,
      requestUri: request?.redirectUri,
      match: redirectUri === request?.redirectUri,
      verifierLen: (request as unknown as { codeVerifier?: string } | null)?.codeVerifier?.length ?? 0,
    });
  }

  return { request, response, promptAsync, redirectUri };
}
