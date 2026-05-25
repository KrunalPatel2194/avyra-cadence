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

// Google's iOS OAuth client ID looks like:
//   226986045351-abc.apps.googleusercontent.com
// The redirect URI it requires is the reverse-DNS form:
//   com.googleusercontent.apps.226986045351-abc:/oauthredirect
// This URL scheme MUST also be registered in iOS Info.plist (see app.json).
const reversedClientId = config.googleIosClientId
  ? `com.googleusercontent.apps.${config.googleIosClientId.replace(".apps.googleusercontent.com", "")}`
  : "";

const explicitRedirectUri = reversedClientId
  ? AuthSession.makeRedirectUri({ native: `${reversedClientId}:/oauthredirect` })
  : "";

export function useGoogleAuthRequest() {
  const [request, response, promptAsync] = Google.useAuthRequest({
    iosClientId: config.googleIosClientId || undefined,
    scopes: ["openid", "profile", "email", GMAIL_SCOPE],
    redirectUri: explicitRedirectUri || undefined,
    extraParams: {
      access_type: "offline",
      prompt: "consent",          // force consent so a refresh_token is returned
    },
  });

  // Whatever URI the request was built with is what we must send to the
  // backend for the code exchange (Google checks redirect_uri matches).
  const redirectUri = request?.redirectUri ?? explicitRedirectUri;

  return { request, response, promptAsync, redirectUri };
}
