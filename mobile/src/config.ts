// Mobile config — reads EXPO_PUBLIC_* env vars at build time.
// To change: edit `.env`, then `npx expo prebuild --clean && npx expo run:ios`.

const apiUrl = "https://sail-nurses-varied-transportation.trycloudflare.com";

// iOS OAuth client id (for the native Google Sign-In SDK).
const googleIosClientId = "226986045351-11sa15i7d2dlhla6l7tfo2a8ommp558v.apps.googleusercontent.com";

// Web OAuth client id — REQUIRED for native sign-in.
// Used by the SDK to get a `serverAuthCode` that cadence-api exchanges (with
// the Web client secret) for a refresh token. Create one in Google Console:
// Application type = Web application; leave redirect URIs empty.
const googleWebClientId = "417755717114-09qf0gimrafdq02s6e71b49sq5coub65.apps.googleusercontent.com";

export const config = {
  apiUrl,
  googleIosClientId,
  googleWebClientId,
  redirectScheme: "cadence",
};
