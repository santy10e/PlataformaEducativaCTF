// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App, queryClient } from "../../app/App";

type Call = { method: string; path: string; body: unknown; csrf: string | null };
const student = { id: 7, username: "ana", display_name: "Ana Estudiante", csrf_token: "csrf", must_change_password: false, roles: ["STUDENT"], permissions: ["course.view", "activity.submit"] };
const teacher = { id: 2, username: "prof", display_name: "Pablo Profe", csrf_token: "csrf", must_change_password: false, roles: ["INSTRUCTOR"], permissions: ["course.view", "course.manage", "activity.review", "class.view", "challenge.view", "event.manage"] };

const lesson = {
  public_id: "les-1",
  title: "La terminal",
  content_markdown: "Texto **propio** de la lección",
  estimated_minutes: 20,
  module: { public_id: "mod-1", title: "Mes 1" },
  course: { public_id: "cur-1", title: "Ciberseguridad" },
  activities: [
    {
      public_id: "act-quiz", type: "quiz", type_label: "Cuestionario", title: "Comprueba lo leído", description_markdown: "", points: 100, xp: 10, category: null, difficulty: null,
      locked: false, lock_reason: null, status: "NOT_STARTED", score: null, max_score: null, attempts: 0, feedback: "", submission: {}, ctf: null,
      config: { max_attempts: 2, questions: [{ id: "q1", prompt: "¿Qué lista archivos?", kind: "single", options: ["ls", "cd"], points: 1 }, { id: "q2", prompt: "Puerto de HTTPS", kind: "text", points: 1 }] },
      hints: [{ id: 31, order: 1, cost: 5, unlocked: false, content_markdown: null }],
    },
    {
      public_id: "act-locked", type: "exercise", type_label: "Ejercicio", title: "Segundo paso", description_markdown: "", points: 20, xp: 0, category: null, difficulty: null,
      locked: true, lock_reason: "Completa primero: Comprueba lo leído", status: "NOT_STARTED", score: null, max_score: null, attempts: 0, feedback: "", submission: {}, ctf: null, config: {}, hints: [],
    },
  ],
};
const template = { id: 1, public_id: "tpl", title: "Ciberseguridad — plan de 9 meses", description_markdown: "Plantilla", status: "DRAFT", is_template: true, can_manage: false, class_ids: [], class_names: [], module_count: 9 };

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
}

function installApi(user: typeof student) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const request = input instanceof Request ? input : new Request(String(input));
    const path = new URL(request.url).pathname;
    const body = request.method === "GET" ? null : await request.clone().text().then((t) => (t ? JSON.parse(t) : null));
    calls.push({ method: request.method, path, body, csrf: request.headers.get("x-csrf-token") });
    if (path.endsWith("/auth/me")) return json(user);
    if (path === "/api/v1/learn/lessons/les-1") return json(lesson);
    if (path === "/api/v1/learn/activities/act-quiz/submit") return json({ status: "APPROVED", score: 50, max_score: 100, feedback: "1/2 puntos de preguntas", attempts: 1, details: {} });
    if (path === "/api/v1/learn/activities/act-quiz/hints/31") return json(lesson.activities[0]);
    if (path === "/api/v1/curriculum/courses" && request.method === "GET") return json([template]);
    if (path === "/api/v1/curriculum/courses/1") return json({ ...template, modules: [{ id: 5, public_id: "m", course_id: 1, title: "Mes 1 · Linux", description_markdown: "", sort_order: 1, status: "PUBLISHED", lessons: [] }] });
    if (path === "/api/v1/curriculum/courses/1/duplicate") return json({ ...template, id: 2, title: "Copia", is_template: false, can_manage: true });
    return json({ items: [], total: 0, page: 1, page_size: 25 });
  }));
  document.cookie = "cyberlab_csrf=csrf";
  return calls;
}

function open(path: string) {
  window.history.replaceState({}, "", path);
  return render(<App />);
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

describe("learner lesson", () => {
  it("submits quiz answers in the API shape with the CSRF header", async () => {
    const calls = installApi(student);
    open("/learn/lessons/les-1");
    expect(await screen.findByRole("heading", { name: "La terminal" })).toBeTruthy();
    const quiz = screen.getByRole("heading", { name: "Comprueba lo leído" }).closest("article")!;
    fireEvent.click(within(quiz).getByLabelText("ls"));
    fireEvent.change(within(quiz).getByLabelText("Respuesta a la pregunta 2"), { target: { value: "443" } });
    fireEvent.click(within(quiz).getByRole("button", { name: /enviar respuestas/i }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/act-quiz/submit"))).toBe(true));
    const sent = calls.find((c) => c.path.endsWith("/act-quiz/submit"))!;
    expect(sent.body).toEqual({ answers: { q1: 0, q2: "443" } });
    expect(sent.csrf).toBe("csrf");
  });

  it("shows why an activity is locked and the hint cost before unlocking it", async () => {
    const calls = installApi(student);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    open("/learn/lessons/les-1");
    expect(await screen.findByText("Completa primero: Comprueba lo leído")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Desbloquear pista 1 (−5 pts)" }));
    expect(window.confirm).toHaveBeenCalledWith("Esta pista cuesta 5 puntos. ¿Desbloquearla?");
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/act-quiz/hints/31"))).toBe(true));
  });
});

describe("curriculum studio", () => {
  it("keeps shared templates read-only and duplicates them for the teacher", async () => {
    const calls = installApi(teacher);
    open("/teaching/curriculum");
    expect(await screen.findByText("Plantilla compartida: solo la administración la edita.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Módulo$/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /guardar curso/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /duplicar para mi clase/i }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/v1/curriculum/courses/1/duplicate")).toBe(true));
  });

  it("sends staff who open the learner area to the studio", async () => {
    installApi(teacher);
    open("/learn");
    expect(await screen.findByRole("heading", { name: "Currículo" })).toBeTruthy();
  });
});
