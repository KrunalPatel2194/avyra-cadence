// Push registration — asks for permission, fetches the iOS device token, and
// posts it to cadence-api. Called from the root layout after sign-in.
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { api } from "@/api/client";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPush(): Promise<string | null> {
  if (Platform.OS !== "ios") {
    // Android comes later (Step beyond v1).
    return null;
  }

  const settings = await Notifications.getPermissionsAsync();
  let granted = settings.granted;
  if (!granted) {
    const ask = await Notifications.requestPermissionsAsync();
    granted = ask.granted;
  }
  if (!granted) return null;

  try {
    const token = await Notifications.getDevicePushTokenAsync();
    if (!token?.data) return null;
    await api.post("/devices", { platform: "ios", push_token: token.data });
    return token.data;
  } catch (e) {
    // Expo Go / simulator can't fetch a real APNs token — that's expected.
    return null;
  }
}
