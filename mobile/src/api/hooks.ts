// TanStack Query hooks — one per route, used by the screens.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  DigestOut, EmailDetail, EmailListResponse, TaskCreate, TaskOut, TaskStatus, User,
} from "./types";

export const qk = {
  me:           ["me"] as const,
  emails:       (cursor?: string | null) => ["emails", cursor ?? "first"] as const,
  email:        (id: string) => ["email", id] as const,
  tasks:        (status: string, due: string, source: string) =>
                  ["tasks", status, due, source] as const,
  digest:       ["digest", "today"] as const,
};

// ── Auth ──────────────────────────────────────────────────────────────────
export function useMe() {
  return useQuery({
    queryKey: qk.me,
    queryFn: () => api.get<User>("/auth/me"),
    staleTime: 60_000,
  });
}

// ── Emails ────────────────────────────────────────────────────────────────
export function useEmails(cursor?: string | null) {
  return useQuery({
    queryKey: qk.emails(cursor),
    queryFn: () => {
      const qs = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
      return api.get<EmailListResponse>(`/emails${qs}`);
    },
  });
}

export function useEmail(id: string | undefined) {
  return useQuery({
    queryKey: qk.email(id || ""),
    queryFn: () => api.get<EmailDetail>(`/emails/${id}`),
    enabled: !!id,
  });
}

export function useRefreshEmails() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ queued: boolean }>("/emails/refresh"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["emails"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

// ── Tasks ─────────────────────────────────────────────────────────────────
export function useTasks(
  status: "open" | "done" | "snoozed" | "all" = "open",
  due: "today" | "week" | "overdue" | "all" = "all",
  source: "email" | "manual" | "news" | "all" = "all",
) {
  return useQuery({
    queryKey: qk.tasks(status, due, source),
    queryFn: () =>
      api.get<TaskOut[]>(
        `/tasks?status=${status}&due=${due}&source=${source}&limit=200`,
      ),
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TaskCreate) => api.post<TaskOut>("/tasks", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<TaskOut> & { status?: TaskStatus } }) =>
      api.patch<TaskOut>(`/tasks/${id}`, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["emails"] });
    },
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/tasks/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

// ── Digest ────────────────────────────────────────────────────────────────
export function useDigestToday() {
  return useQuery({
    queryKey: qk.digest,
    queryFn: () => api.get<DigestOut>("/digest/today"),
  });
}

export function useGenerateDigest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ queued: boolean }>("/digest/generate"),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.digest }),
  });
}

// ── Devices ───────────────────────────────────────────────────────────────
export function useRegisterDevice() {
  return useMutation({
    mutationFn: (body: { platform: "ios" | "android"; push_token: string }) =>
      api.post<{ ok: boolean }>("/devices", body),
  });
}
