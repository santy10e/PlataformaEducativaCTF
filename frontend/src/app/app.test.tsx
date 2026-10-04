// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App, queryClient } from "./App";
import { CommandPalette, DataTable } from "../components/ui";
import type { ColumnDef } from "@tanstack/react-table";

const student = {
  id: 7,
  username: "student",
  display_name: "Ana Estudiante",
  csrf_token: "csrf",
  roles: ["STUDENT"],
  permissions: ["challenge.view", "event.view"],
};
function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
}
function installApiMock(initiallyAuthenticated = false) {
  let authenticated = initiallyAuthenticated;
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
    if (url.endsWith("/auth/me"))
      return authenticated
        ? jsonResponse(student)
        : jsonResponse(
            {
              error: {
                code: "AUTHENTICATION_REQUIRED",
                message: "login required",
                details: {},
              },
            },
            401,
          );
    if (url.endsWith("/auth/login")) {
      authenticated = true;
      return jsonResponse({
        id: student.id,
        username: student.username,
        display_name: student.display_name,
        csrf_token: "csrf",
      });
    }
    return jsonResponse(
      {
        error: {
          code: "RESOURCE_NOT_FOUND",
          message: "not found",
          details: {},
        },
      },
      404,
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  queryClient.clear();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
  document.documentElement.dataset.theme = "light";
});

describe("frontend session and route shell", () => {
  it("sends signed-out visitors to the real login screen", async () => {
    installApiMock();
    window.history.replaceState({}, "", "/workspace");
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "Iniciar sesión" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("Usuario")).toBeTruthy();
  });

  it("authenticates, refreshes the session and opens the private workspace", async () => {
    const fetchMock = installApiMock();
    window.history.replaceState({}, "", "/login");
    render(<App />);
    await screen.findByRole("heading", { name: "Iniciar sesión" });
    fireEvent.change(screen.getByLabelText("Usuario"), {
      target: { value: "student" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "classroom-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /entrar al campus/i }));
    expect(
      await screen.findByRole("heading", { name: "Hola, Ana." }),
    ).toBeTruthy();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        (typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url
        ).includes("/auth/login"),
      ),
    ).toBe(true);
  });

  it("blocks a route the current role is not permitted to open", async () => {
    installApiMock(true);
    window.history.replaceState({}, "", "/roles");
    render(<App />);
    expect(
      await screen.findByText(/403\s+\/\s+ACCESO RESTRINGIDO/),
    ).toBeTruthy();
  });
});

describe("shared interaction components", () => {
  it("filters the TanStack table from its search field", () => {
    type Sample = { name: string };
    const columns: ColumnDef<Sample, unknown>[] = [
      { accessorKey: "name", header: "Práctica" },
    ];
    render(
      <DataTable
        columns={columns}
        data={[{ name: "Análisis web" }, { name: "Ecos en la red" }]}
      />,
    );
    fireEvent.change(
      screen.getByRole("textbox", { name: "Buscar en la tabla" }),
      { target: { value: "Ecos" } },
    );
    expect(screen.getByText("Ecos en la red")).toBeTruthy();
    expect(screen.queryByText("Análisis web")).toBeNull();
  });

  it("opens and closes the command palette with the keyboard", async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Open</button>
          <CommandPalette
            open={open}
            onOpenChange={setOpen}
            items={[{ label: "Mi espacio", action: () => setOpen(false) }]}
          />
        </>
      );
    }
    render(<Harness />);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(await screen.findByRole("dialog")).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
