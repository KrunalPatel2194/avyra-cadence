// Google OAuth via expo-auth-session (PKCE). On success we send {code,
// codeVerifier, redirectUri} to cadence-api which performs the actual token
// exchange (server-side, where the client secret lives).
import * as AuthSession from "expo-auth-session";
import * as Google from "expo-auth-session/providers/google";
import { useEffect, useMemo } from "react";

import { config } from "@/config";

const GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly";

export function useGoogleAuthRequest() {
  // expo-auth-session expects either iosClientId or expoClientId. We use the
  // iOS native client id and the PKCE response_type=code flow.
  const [request, response, promptAsync] = Google.useAuthRequest({
    iosClientId: config.googleIosClientId || undefined,
    scopes: ["openid", "profile", "email", GMAIL_SCOPE],
    responseType: AuthSession.ResponseType.Code,
    extraParams: {
      access_type: "offline",
      prompt: "consent",          // force consent so a refresh_token is returned
    },
    usePKCE: true,
    redirectUri: AuthSession.makeRedirectUri({ scheme: config.redirectScheme, path: "oauth2redirect" }),
  });

  const redirectUri = useMemo(
    () => AuthSession.makeRedirectUri({ scheme: config.redirectScheme, path: "oauth2redirect" }),
    [],
  );

  // Surface request-readiness so the UI button can stay disabled until config
  // is loaded.
  useEffect(() => {}, [request]);

  return { request, response, promptAsync, redirectUri };
}
