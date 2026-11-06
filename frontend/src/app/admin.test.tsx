// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App, queryClient } from "./App";
import { routes } from "./routes";

const allPermissions = ["activity.review", "audit.view", "challenge.create", "challenge.view", "course.manage", "course.view", "event.manage", "event.view", "role.update", "role.view", "scoreboard.manage", "scoreboard.view", "settings.update", "settings.view", "user.view", "class.view"];
const admin = { id: 1, username: "admin", display_name: "Rosa Admin", csrf_token: "csrf", must_change_password: false, roles: ["ADMIN"], permissions: allPermissions };
const instructor = { ...admin, id: 2, username: "prof", display_name: "Pablo Profe", roles: ["INSTRUCTOR"], permissions: ["event.manage", "scoreboard.view", "scoreboard.manage", "class.view", "challenge.view", "event.view"] };

type Call = { method: string; path: string; body: unknown; csrf: string | null };

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
}

function installApi(user: typeof admin) {
  const calls: Call[] = [];
  const settings = [
    { key: "scoreboard_enabled", value: true, description: "Visibilidad general del scoreboard" },
    { key: "max_attempts_global", value: 20, description: "Intentos máximos por reto y estudiante" },
  ];
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const request = input instanceof Request ? input : new Request(String(input));
    const url = new URL(request.url);
    const body = request.method === "GET" ? null : await request.clone().text().then((t) => (t ? JSON.parse(t) : null));
    calls.push({ method: request.method, path: url.pathname, body, csrf: request.headers.get("x-csrf-token") });
    const path = url.pathname;
    if (path.endsWith("/auth/me")) return json(user);
    if (path.endsWith("/admin/settings")) return json(settings);
    if (path.startsWith("/api/v1/admin/settings/")) return json({ key: path.split("/").pop(), value: (body as { value: unknown }).value });
    if (path.endsWith("/admin/roles"))
      return json([
        { id: 1, name: "ADMIN", is_system: true, permissions: allPermissions },
        { id: 2, name: "INSTRUCTOR", is_system: true, permissions: ["event.manage", "class.view"] },
      ]);
    if (path.startsWith("/api/v1/admin/roles/")) return json({ id: 2, name: "INSTRUCTOR", permissions: (body as { permissions: string[] }).permissions });
    if (path.endsWith("/admin/audit"))
      return json({ items: [{ id: 9, action: "LOGIN_FAILED", actor_user_id: null, target_type: null, target_id: null, meta: { ip: "10.0.0.4" }, created_at: "2026-10-03T10:00:00" }], total: 1, page: 1, page_size: 50 });
    if (path.endsWith("/ctf/scoreboard"))
      return json({ scope: "GLOBAL", scope_id: "0", frozen: true, items: [{ rank: 1, display_name: "Carla Uno", score: 90, grade: { grade: 2, label: "Básico" } }] });
    if (path.endsWith("/classes")) return json({ items: [{ id: 4, name: "10A", academic_period: "2026" }], total: 1, page: 1, page_size: 100 });
    if (path.endsWith("/ctf/events")) return json({ items: [], total: 0, page: 1, page_size: 100 });
    return json({ items: [], total: 0, page: 1, page_size: 25 });
  });
  vi.stubGlobal("fetch", fetchMock);
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
  window.history.replaceState({}, "", "/");
});

describe("administration screens", () => {
  it("edits a boolean setting immediately with the CSRF header", async () => {
    const calls = installApi(admin);
    open("/settings");
    const toggle = await screen.findByRole("switch");
    fireEvent.click(toggle);
    await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.path === "/api/v1/admin/settings/scoreboard_enabled")).toBe(true));
    const put = calls.find((c) => c.method === "PUT")!;
    expect(put.body).toEqual({ value: false });
    expect(put.csrf).toBe("csrf");
  });

  it("keeps the administrator role read-only and saves another role's permissions", async () => {
    const calls = installApi(admin);
    open("/roles");
    const adminCard = (await screen.findByRole("heading", { name: "ADMIN" })).closest("article")!;
    expect(within(adminCard).getByText("Protegido")).toBeTruthy();
    expect(within(adminCard).getAllByRole("checkbox").every((box) => box.hasAttribute("disabled"))).toBe(true);

    const instructorCard = screen.getByRole("heading", { name: "INSTRUCTOR" }).closest("article")!;
    fireEvent.click(within(instructorCard).getByRole("checkbox", { name: "audit.view" }));
    fireEvent.click(within(instructorCard).getByRole("button", { name: "Guardar permisos" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.path === "/api/v1/admin/roles/2")).toBe(true));
    expect((calls.find((c) => c.method === "PUT")!.body as { permissions: string[] }).permissions).toEqual(["audit.view", "class.view", "event.manage"]);
  });

  it("lists audit entries", async () => {
    installApi(admin);
    open("/audit");
    expect(await screen.findByText("LOGIN_FAILED")).toBeTruthy();
    expect(screen.getByText(/Página 1 de 1/)).toBeTruthy();
  });

  it("shows the campus scoreboard to administrators with its frozen state", async () => {
    installApi(admin);
    open("/scoreboard");
    expect(await screen.findByText("Carla Uno")).toBeTruthy();
    expect(screen.getByText(/Congelado/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Todo el campus" })).toBeTruthy();
  });

  it("asks instructors to pick a class or event instead of a campus-wide board", async () => {
    installApi(instructor);
    open("/scoreboard");
    expect(await screen.findByText("Elige qué marcador ver")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Todo el campus" })).toBeNull();
  });
});

describe("staff navigation", () => {
  it("hides the learner-only entries and never renders a placeholder page", async () => {
    installApi(admin);
    open("/workspace");
    const nav = await screen.findByRole("navigation", { name: "Navegación principal" });
    expect(within(nav).queryByText("Retos")).toBeNull();
    expect(within(nav).queryByText("Eventos")).toBeNull();
    expect(within(nav).getByText("Marcador")).toBeTruthy();
    expect(screen.queryByText(/permisos de esta sesión/i)).toBeNull();
  });

  it.each(routes.map((route) => route.path))("route %s has a real screen", async (path) => {
    installApi(admin);
    const view = open(path);
    await screen.findByRole("navigation", { name: "Navegación principal" });
    await waitFor(() => expect(view.container.querySelector(".workspace-content")?.textContent?.length).toBeGreaterThan(0));
    expect(view.container.textContent).not.toMatch(/se está preparando|Fase \d|FASE \d/);
    view.unmount();
  });
});
