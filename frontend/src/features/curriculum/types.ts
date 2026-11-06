export type Status = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export type ActivityKind = "lesson_read" | "quiz" | "exercise" | "project" | "ctf_challenge";
export type ProgressStatus = "NOT_STARTED" | "IN_PROGRESS" | "PENDING_REVIEW" | "NEEDS_CHANGES" | "APPROVED" | "REJECTED" | "UNAVAILABLE";

export type QuizQuestion = {
  id: string;
  prompt: string;
  kind: "single" | "multiple" | "text";
  options?: string[];
  correct?: number[];
  accepted?: string[];
  points: number;
};

export type Hint = { id: number; order: number; cost: number; content_markdown: string };

export type StaffActivity = {
  id: number;
  public_id: string;
  lesson_id: number;
  type: ActivityKind;
  title: string;
  description_markdown: string;
  sort_order: number;
  category_id: number | null;
  difficulty_id: number | null;
  points: number;
  xp: number;
  status: Status;
  config: Record<string, unknown>;
  prerequisite_ids: number[];
  hints: Hint[];
};
export type StaffLesson = { id: number; public_id: string; module_id: number; title: string; content_markdown: string; estimated_minutes: number | null; sort_order: number; status: Status; activities: StaffActivity[] };
export type StaffModule = { id: number; public_id: string; course_id: number; title: string; description_markdown: string; sort_order: number; status: Status; lessons: StaffLesson[] };
export type StaffCourse = {
  id: number;
  public_id: string;
  title: string;
  description_markdown: string;
  status: Status;
  is_template: boolean;
  can_manage: boolean;
  class_ids: number[];
  class_names: string[];
  module_count: number;
  modules?: StaffModule[];
};

export type ReviewRow = {
  id: number;
  status: ProgressStatus;
  student: string;
  activity: string;
  activity_type: ActivityKind;
  points: number;
  course: string;
  submission: { text?: string; url?: string; answer?: string };
  submitted_at: string | null;
  attempts: number;
  feedback: string;
  score: number | null;
};
export type CourseProgress = {
  modules: { public_id: string; title: string }[];
  students: { student_id: number; display_name: string; pending_review: boolean; modules: { module_public_id: string; completed: number; total: number }[] }[];
};

export type LearnerHint = { id: number; order: number; cost: number; unlocked: boolean; content_markdown: string | null };
export type LearnerActivity = {
  public_id: string;
  type: ActivityKind;
  type_label: string;
  title: string;
  description_markdown: string;
  points: number;
  xp: number;
  category: string | null;
  difficulty: string | null;
  locked: boolean;
  lock_reason: string | null;
  config: { questions?: QuizQuestion[]; max_attempts?: number | null; review?: "manual" | "automatic"; accept?: ("text" | "url")[] };
  status: ProgressStatus;
  score: number | null;
  max_score: number | null;
  attempts: number;
  feedback: string;
  submission: Record<string, unknown>;
  hints: LearnerHint[];
  ctf: { available: boolean; event_public_id: string | null; challenge_public_id: string | null; state: string } | null;
};
export type LearnerLesson = {
  public_id: string;
  title: string;
  content_markdown: string;
  estimated_minutes: number | null;
  module: { public_id: string; title: string };
  course: { public_id: string; title: string };
  activities: LearnerActivity[];
};
export type OutlineActivity = { public_id: string; title: string; type: ActivityKind; status: ProgressStatus; locked: boolean };
export type CourseOutline = {
  public_id: string;
  title: string;
  description_markdown: string;
  modules: { public_id: string; title: string; description_markdown: string; completed: number; total: number; lessons: { public_id: string; title: string; estimated_minutes: number | null; activities: OutlineActivity[] }[] }[];
};

export const statusLabel: Record<ProgressStatus, string> = {
  NOT_STARTED: "Por empezar",
  IN_PROGRESS: "En curso",
  PENDING_REVIEW: "En revisión",
  NEEDS_CHANGES: "Requiere cambios",
  APPROVED: "Completada",
  REJECTED: "No aprobada",
  UNAVAILABLE: "No disponible",
};
export const kindLabel: Record<ActivityKind, string> = {
  lesson_read: "Lectura",
  quiz: "Cuestionario",
  exercise: "Ejercicio",
  project: "Proyecto",
  ctf_challenge: "Reto CTF",
};
export const publishLabel: Record<Status, string> = { DRAFT: "Borrador", PUBLISHED: "Publicado", ARCHIVED: "Archivado" };
