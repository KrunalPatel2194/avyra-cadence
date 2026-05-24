// Wire shapes returned by cadence-api. Kept narrow on purpose — fields the
// mobile UI doesn't render don't belong here.

export type User = {
  id: string;
  email: string;
  name: string;
  tz: string;
  gmail_linked: boolean;
};

export type ExchangeResponse = {
  jwt: string;
  user: User;
};

export type EmailListItem = {
  id: string;
  gmail_msg_id: string;
  from_addr: string;
  subject: string;
  received_at: string;
  summary: string | null;
  is_urgent: boolean;
  category: string | null;
  task_count: number;
  processed: boolean;
};

export type EmailListResponse = {
  items: EmailListItem[];
  next_cursor: string | null;
};

export type EmailDetail = EmailListItem & {
  gmail_thread_id: string | null;
  snippet: string;
  body_text: string;
  summary_model: string | null;
  processed_at: string | null;
  tasks: TaskOut[];
};

export type TaskSource = "email" | "news" | "manual";
export type TaskPriority = "low" | "med" | "high";
export type TaskStatus = "open" | "done" | "snoozed" | "deleted";

export type TaskOut = {
  id: string;
  source_type: TaskSource;
  source_ref: string | null;
  title: string;
  notes: string;
  due_date: string | null;
  due_time: string | null;
  remind_at: string | null;
  priority: TaskPriority;
  status: TaskStatus;
  confidence: number | null;
  rationale: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskCreate = {
  title: string;
  notes?: string;
  due_date?: string | null;
  due_time?: string | null;
  remind_at?: string | null;
  priority?: TaskPriority;
};

export type DigestOut = {
  id: string;
  date: string;
  body_md: string;
  highlights: string[];
  generated_at: string;
  delivered_at: string | null;
} | null;
