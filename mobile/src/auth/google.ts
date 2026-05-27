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

import { config } from "@/config";

const GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly";

// iOS OAuth with Google requires the reverse-DNS scheme as redirect_uri.
// The provider defaults to exp:// in dev mode, but Google won't accept that.
const getIosRedirectUri = () => {
  if (!config.googleIosClientId) return "";
  const clientIdPart = config.googleIosClientId.replace(".apps.googleusercontent.com", "");
  return `com.googleusercontent.apps.${clientIdPart}://oauthredirect`;
};

export function useGoogleAuthRequest() {
  const redirectUri = getIosRedirectUri();

  const [request, response, promptAsync] = Google.useAuthRequest({
    iosClientId: config.googleIosClientId || undefined,
    scopes: ["openid", "profile", "email", GMAIL_SCOPE],
    redirectUri, // Explicitly set to iOS scheme; prevents exp:// default in dev
    extraParams: {
      access_type: "offline",
      prompt: "consent",
    },
  });

  console.log("OAuth request built.", {
    computed_redirectUri: redirectUri,
    request_redirectUri: request?.redirectUri,
    match: redirectUri === request?.redirectUri,
  });

  return { request, response, promptAsync, redirectUri };
}
