// API client for cadence-api. JWT is read from secure storage; one place for
// auth headers and error normalization.
import * as SecureStore from "expo-secure-store";

import { config } from "@/config";

const JWT_KEY = "cadence.jwt";

export type ApiError = { status: number; detail: string };

async function readJwt(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(JWT_KEY);
  } catch {
    return null;
  }
}

export async function saveJwt(jwt: string): Promise<void> {
  await SecureStore.setItemAsync(JWT_KEY, jwt);
}

export async function clearJwt(): Promise<void> {
  await SecureStore.deleteItemAsync(JWT_KEY);
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function request<T>(method: Method, path: string, body?: unknown, opts: { auth?: boolean } = { auth: true }): Promise<T> {
  const url = `${config.apiUrl}${path}`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.auth !== false) {
    const jwt = await readJwt();
    if (jwt) headers.Authorization = `Bearer ${jwt}`;
  }
  let resp: Response;
  try {
    resp = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "network error";
    throw { status: 0, detail: message } as ApiError;
  }

  if (resp.status === 204) return undefined as T;
  const text = await resp.text();
  let parsed: unknown = null;
  if (text) {
    try { parsed = JSON.parse(text); } catch { parsed = text; }
  }

  if (!resp.ok) {
    const detail =
      parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as { detail: unknown }).detail)
        : text || resp.statusText;
    throw { status: resp.status, detail } as ApiError;
  }
  return parsed as T;
}

export const api = {
  get:    <T>(path: string, opts?: { auth?: boolean }) => request<T>("GET", path, undefined, opts),
  post:   <T>(path: string, body?: unknown, opts?: { auth?: boolean }) => request<T>("POST", path, body, opts),
  patch:  <T>(path: string, body?: unknown, opts?: { auth?: boolean }) => request<T>("PATCH", path, body, opts),
  delete: <T>(path: string, opts?: { auth?: boolean }) => request<T>("DELETE", path, undefined, opts),
};
