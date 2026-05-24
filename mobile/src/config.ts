// Mobile config — reads EXPO_PUBLIC_* env vars at build time.
// To change: edit `.env`, then `npx expo prebuild --clean && npx expo run:ios`.

const apiUrl = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8010";
const googleIosClientId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || "";

export const config = {
  apiUrl,
  // iOS OAuth client id from Google Cloud Console. PKCE auth happens on the
  // device; cadence-api exchanges the code with this same id (no client
  // secret — iOS clients don't have one) and verifies id_token audience.
  googleIosClientId,
  // Custom URL scheme — must match app.json `scheme` and the iOS client's
  // configured redirect URI in Google Cloud Console.
  redirectScheme: "cadence",
};
