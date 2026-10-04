import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Check,
  FileUp,
  Plus,
  Search,
  UsersRound,
} from "lucide-react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { api, unwrap } from "../api/client";
import { Button, Badge, EmptyState, toast } from "../components/ui";
import { useAuth } from "./AuthProvider";

type Person = {
  id: number;
  username: string;
  display_name: string;
  first_name: string;
  last_name: string;
  email: string | null;
  roles: string[];
  is_active: boolean;
  must_change_password: boolean;
  class_ids: number[];
};
type PersonPage = {
  items: Person[];
  total: number;
  page: number;
  page_size: number;
};
type SchoolClass = {
  id: number;
  name: string;
  academic_period: string;
  description: string;
  teacher_user_id: number | null;
  teacher_name: string | null;
  student_count: number;
};
type ClassPage = {
  items: SchoolClass[];
  total: number;
  page: number;
  page_size: number;
};
type ImportRow = {
  row_number: number;
  username: string;
  display_name: string;
  course: string;
  email: string | null;
  valid: boolean;
  errors: string[];
};
type Preview = {
  job_id: string;
  status: string;
  row_count: number;
  valid_count: number;
  error_count: number;
  items: ImportRow[];
};

const personSchema = z.object({
  username: z.string().min(3).max(80),
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  email: z.union([z.string().email(), z.literal("")]),
  password: z.string().min(12),
  role: z.enum(["STUDENT", "INSTRUCTOR"]),
  class_id: z.string(),
});
const classSchema = z.object({
  name: z.string().min(2).max(120),
  academic_period: z.string().max(32),
  description: z.string().max(255),
});

export function PeoplePage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [dialog, setDialog] = useState(false);
  const [editing, setEditing] = useState<Person | null>(null);
  const q = useQuery({
    queryKey: ["people", search, role],
    queryFn: async () =>
      (await unwrap(
        await api.GET("/api/v1/users", {
          params: {
            query: {
              page: 1,
              page_size: 100,
              search: search || undefined,
              role: role || undefined,
            },
          },
        }),
      )) as PersonPage,
  });
  const availableClasses = useQuery({
    queryKey: ["class-options"],
    queryFn: async () =>
      (await unwrap(
        await api.GET("/api/v1/classes", {
          params: { query: { page: 1, page_size: 100 } },
        }),
      )) as ClassPage,
  });
  const mutation = useMutation({
    mutationFn: async (v: z.infer<typeof personSchema>) =>
      editing
        ? unwrap(
            await api.PUT("/api/v1/users/{user_id}", {
              params: { path: { user_id: editing.id } },
              body: {
                first_name: v.first_name,
                last_name: v.last_name,
                email: v.email || null,
              },
            }),
          )
        : unwrap(
            await api.POST("/api/v1/users", {
              body: {
                username: v.username,
                password: v.password,
                first_name: v.first_name,
                last_name: v.last_name,
                email: v.email || null,
                role: v.role,
                class_ids: v.class_id ? [Number(v.class_id)] : [],
              },
            }),
          ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["people"] });
      setDialog(false);
      setEditing(null);
      toast(
        editing
          ? "Perfil actualizado."
          : "Perfil creado. La persona deberá cambiar su contraseña al ingresar.",
      );
    },
  });
  const resetPassword = useMutation({
    mutationFn: async (person: Person) => {
      const temporary_password = window.prompt(
        `Nueva contraseña temporal para ${person.username} (mínimo 12 caracteres):`,
      );
      if (!temporary_password) return;
      if (temporary_password.length < 12)
        throw new Error("Usa al menos 12 caracteres.");
      return unwrap(
        await api.POST("/api/v1/users/{user_id}/password-reset", {
          params: { path: { user_id: person.id } },
          body: { temporary_password },
        }),
      );
    },
    onSuccess: () => {
      toast("Contraseña restablecida; deberá cambiarla al ingresar.");
    },
  });
  const toggle = useMutation({
    mutationFn: async (p: Person) =>
      unwrap(
        await api.PATCH("/api/v1/users/{user_id}/status", {
          params: { path: { user_id: p.id } },
          body: { is_active: !p.is_active },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["people"] }),
  });
  const form = useForm<z.infer<typeof personSchema>>({
    resolver: zodResolver(personSchema),
    defaultValues: {
      username: "",
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      role: "STUDENT",
      class_id: "",
    },
  });
  function openCreate() {
    setEditing(null);
    form.reset({
      username: "",
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      role: "STUDENT",
      class_id: "",
    });
    setDialog(true);
  }
  function openEdit(person: Person) {
    setEditing(person);
    form.reset({
      username: person.username,
      first_name: person.first_name,
      last_name: person.last_name,
      email: person.email ?? "",
      password: "TemporaryPass123!",
      role: person.roles.includes("INSTRUCTOR") ? "INSTRUCTOR" : "STUDENT",
      class_id: "",
    });
    setDialog(true);
  }
  function exportCsv() {
    const rows = q.data?.items ?? [];
    const csv = [
      "nombre,usuario,correo,rol,estado",
      ...rows.map((p) =>
        [
          p.display_name,
          p.username,
          p.email ?? "",
          p.roles.join("|"),
          p.is_active ? "activo" : "inactivo",
        ]
          .map((x) => `"${x.replaceAll('"', '""')}"`)
          .join(","),
      ),
    ].join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }),
    );
    a.download = "personas-cyberlab.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  }
  return (
    <>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">DIRECTORIO DEL CAMPUS</p>
        <div className="edu-heading-row">
          <div>
            <h1>Personas</h1>
            <p>Una mirada clara a quiénes aprenden y enseñan aquí.</p>
          </div>
          <div className="edu-actions">
            <Button variant="outline" onClick={exportCsv}>
              <ArrowDownToLine size={15} /> Exportar lista
            </Button>
            <Link className="ui-button ui-outline" to="/import">
              <FileUp size={15} /> Importar CSV
            </Link>
            <Button onClick={openCreate}>
              <Plus size={15} /> Nueva persona
            </Button>
          </div>
        </div>
      </header>
      <section className="edu-statline">
        <span>
          <UsersRound size={17} />
          <strong>{q.data?.total ?? "—"}</strong> perfiles en el directorio
        </span>
        <span className="edu-small-note">PERSONAS · CAMPUS CYBERLAB</span>
      </section>
      <section className="edu-panel">
        <div className="edu-toolbar">
          <label className="edu-search">
            <Search size={15} />
            <input
              aria-label="Buscar personas"
              placeholder="Buscar por nombre o usuario"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <div className="edu-filters">
            <button
              className={!role ? "selected" : ""}
              onClick={() => setRole("")}
            >
              Todas
            </button>
            <button
              className={role === "student" ? "selected" : ""}
              onClick={() => setRole("student")}
            >
              Estudiantes
            </button>
            <button
              className={role === "instructor" ? "selected" : ""}
              onClick={() => setRole("instructor")}
            >
              Profesores
            </button>
          </div>
        </div>
        {q.isLoading ? (
          <div className="edu-empty">Cargando directorio…</div>
        ) : !q.data?.items.length ? (
          <EmptyState
            title="Aún no hay personas"
            description="Los perfiles del campus aparecerán aquí."
          />
        ) : (
          <div className="edu-table-scroll">
            <table className="edu-table">
              <thead>
                <tr>
                  <th>PERSONA</th>
                  <th>PERFIL</th>
                  <th>CLASES</th>
                  <th>ESTADO</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong>{p.display_name}</strong>
                      <small>
                        @{p.username}
                        {p.email ? ` · ${p.email}` : ""}
                      </small>
                    </td>
                    <td>
                      {p.roles.includes("INSTRUCTOR")
                        ? "Profesor"
                        : p.roles.includes("ADMIN")
                          ? "Administrador"
                          : "Estudiante"}
                    </td>
                    <td>
                      {p.class_ids.length
                        ? `${p.class_ids.length} asignadas`
                        : "—"}
                    </td>
                    <td>
                      <Badge status={p.is_active ? "done" : "draft"}>
                        {p.is_active ? "Activo" : "Inactivo"}
                      </Badge>
                      {p.must_change_password && (
                        <small className="edu-hint">
                          Cambio de contraseña pendiente
                        </small>
                      )}
                    </td>
                    <td>
                      <div className="edu-row-actions">
                        <button
                          className="edu-text-action"
                          onClick={() => openEdit(p)}
                        >
                          Editar
                        </button>
                        {can("user.password_reset") && (
                          <button
                            className="edu-text-action"
                            onClick={() => resetPassword.mutate(p)}
                          >
                            Restablecer clave
                          </button>
                        )}
                        <button
                          className="edu-text-action"
                          onClick={() => toggle.mutate(p)}
                        >
                          {p.is_active ? "Desactivar" : "Reactivar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {dialog && (
        <div
          className="edu-modal-backdrop"
          onClick={() => {
            setDialog(false);
            setEditing(null);
          }}
        >
          <form
            className="edu-modal"
            onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="edu-modal-close"
              onClick={() => {
                setDialog(false);
                setEditing(null);
              }}
            >
              ×
            </button>
            <p className="page-eyebrow">
              {editing ? "PERFIL DEL CAMPUS" : "ALTA DE PERFIL"}
            </p>
            <h2>
              {editing ? "Actualizar datos." : "Una nueva voz en el campus."}
            </h2>
            <p className="edu-modal-copy">
              {editing
                ? "Actualiza la información académica del perfil."
                : "La contraseña temporal se cambiará en el primer ingreso."}
            </p>
            <div className="edu-form-grid">
              {(
                [
                  "first_name",
                  "last_name",
                  ...(editing ? [] : ["username", "password"]),
                  "email",
                ] as const
              ).map((key) => {
                const field = key as keyof z.infer<typeof personSchema>;
                return (
                  <label key={key}>
                    {
                      {
                        first_name: "Nombre",
                        last_name: "Apellido",
                        username: "Usuario",
                        email: "Correo electrónico",
                        password: "Contraseña temporal",
                      }[key]
                    }
                    <input
                      className="ui-input"
                      type={key === "password" ? "password" : "text"}
                      {...form.register(field)}
                    />
                    {form.formState.errors[field] && (
                      <small className="edu-error">
                        {form.formState.errors[field]?.message}
                      </small>
                    )}
                  </label>
                );
              })}
              {!editing && (
                <>
                  <label>
                    Tipo de perfil
                    <select className="ui-input" {...form.register("role")}>
                      <option value="STUDENT">Estudiante</option>
                      {can("user.password_reset") && (
                        <option value="INSTRUCTOR">Profesor</option>
                      )}
                    </select>
                  </label>
                  {form.watch("role") === "STUDENT" && (
                    <label>
                      Clase
                      <select
                        className="ui-input"
                        {...form.register("class_id")}
                      >
                        <option value="">Selecciona una clase</option>
                        {availableClasses.data?.items.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                      {form.formState.errors.class_id && (
                        <small className="edu-error">
                          Elige una clase para matricular al estudiante.
                        </small>
                      )}
                    </label>
                  )}
                </>
              )}
            </div>
            {mutation.isError && (
              <p className="edu-error">{mutation.error?.message}</p>
            )}
            <div className="edu-modal-actions">
              <Button
                type="button"
                variant="quiet"
                onClick={() => {
                  setDialog(false);
                  setEditing(null);
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {editing ? "Guardar cambios" : "Crear perfil"}{" "}
                <ArrowRight size={14} />
              </Button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

export function LegacyClassesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const q = useQuery({
    queryKey: ["classes", search],
    queryFn: async () =>
      (await unwrap(
        await api.GET("/api/v1/classes", {
          params: {
            query: { page: 1, page_size: 100, search: search || undefined },
          },
        }),
      )) as ClassPage,
  });
  const create = useMutation({
    mutationFn: async (v: z.infer<typeof classSchema>) =>
      unwrap(
        await api.POST("/api/v1/classes", {
          body: { ...v, teacher_user_id: null },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      setOpen(false);
      toast("Clase creada.");
    },
  });
  const form = useForm<z.infer<typeof classSchema>>({
    resolver: zodResolver(classSchema),
    defaultValues: { name: "", academic_period: "", description: "" },
  });
  return (
    <>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">VIDA ACADÉMICA</p>
        <div className="edu-heading-row">
          <div>
            <h1>Clases</h1>
            <p>
              Grupos pequeños para aprender, practicar y compartir hallazgos.
            </p>
          </div>
          <Button onClick={() => setOpen(true)}>
            <Plus size={15} /> Nueva clase
          </Button>
        </div>
      </header>
      <section className="edu-statline">
        <span>
          <BookOpen size={17} />
          <strong>{q.data?.total ?? "—"}</strong> espacios de aprendizaje
        </span>
        <label className="edu-search">
          <Search size={15} />
          <input
            placeholder="Buscar una clase"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </section>
      <section className="edu-class-grid">
        {q.data?.items.map((c, i) => (
          <article className="edu-class-card" key={c.id}>
            <div className="edu-class-index">
              SEMINARIO {String(i + 1).padStart(2, "0")}
              <span>↗</span>
            </div>
            <h2>{c.name}</h2>
            <p>{c.description || "Un espacio para aprender haciendo."}</p>
            <div className="edu-class-meta">
              <span>{c.academic_period || "Periodo por definir"}</span>
              <span>{c.student_count} estudiantes</span>
            </div>
            <div className="edu-class-teacher">
              {c.teacher_name ?? "Docente por asignar"} <ArrowRight size={14} />
            </div>
          </article>
        ))}
      </section>
      {!q.isLoading && !q.data?.items.length && (
        <EmptyState
          title="Tu campus empieza aquí"
          description="Crea la primera clase para reunir a estudiantes y docentes."
        />
      )}
      {open && (
        <div className="edu-modal-backdrop" onClick={() => setOpen(false)}>
          <form
            className="edu-modal"
            onSubmit={form.handleSubmit((v) => create.mutate(v))}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="edu-modal-close"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
            <p className="page-eyebrow">NUEVO ESPACIO DE APRENDIZAJE</p>
            <h2>Crear una clase.</h2>
            <label>
              Nombre
              <input className="ui-input" {...form.register("name")} />
            </label>
            <label>
              Periodo académico
              <input
                className="ui-input"
                placeholder="2026 · Segundo semestre"
                {...form.register("academic_period")}
              />
            </label>
            <label>
              Descripción
              <textarea
                className="ui-input"
                {...form.register("description")}
              />
            </label>
            <div className="edu-modal-actions">
              <Button
                variant="quiet"
                type="button"
                onClick={() => setOpen(false)}
              >
                Cancelar
              </Button>
              <Button type="submit">Crear clase</Button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

export function ClassManagementPage() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<SchoolClass | null>(null);
  const [editingOpen, setEditingOpen] = useState(false);
  const [roster, setRoster] = useState<SchoolClass | null>(null);
  const [memberIds, setMemberIds] = useState<number[]>([]);
  const q = useQuery({
    queryKey: ["classes", search],
    queryFn: async () =>
      (await unwrap(
        await api.GET("/api/v1/classes", {
          params: {
            query: { page: 1, page_size: 100, search: search || undefined },
          },
        }),
      )) as ClassPage,
  });
  const students = useQuery({
    queryKey: ["class-candidates", roster?.id],
    enabled: !!roster,
    queryFn: async () =>
      (await unwrap(
        await api.GET("/api/v1/users", {
          params: { query: { page: 1, page_size: 100, role: "student" } },
        }),
      )) as PersonPage,
  });
  const currentMembers = useQuery({
    queryKey: ["class-members", roster?.id],
    enabled: !!roster,
    queryFn: async () =>
      (await unwrap(
        await api.GET("/api/v1/classes/{class_id}/students", {
          params: { path: { class_id: roster!.id } },
        }),
      )) as Person[],
  });
  const form = useForm<z.infer<typeof classSchema>>({
    resolver: zodResolver(classSchema),
    defaultValues: { name: "", academic_period: "", description: "" },
  });
  const save = useMutation({
    mutationFn: async (v: z.infer<typeof classSchema>) =>
      editing
        ? unwrap(
            await api.PUT("/api/v1/classes/{class_id}", {
              params: { path: { class_id: editing.id } },
              body: { ...v, teacher_user_id: editing.teacher_user_id },
            }),
          )
        : unwrap(
            await api.POST("/api/v1/classes", {
              body: { ...v, teacher_user_id: null },
            }),
          ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      setEditingOpen(false);
      setEditing(null);
      toast(editing ? "Clase actualizada." : "Clase creada.");
    },
  });
  const remove = useMutation({
    mutationFn: async (c: SchoolClass) =>
      unwrap(
        await api.DELETE("/api/v1/classes/{class_id}", {
          params: { path: { class_id: c.id } },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast("Clase eliminada.");
    },
  });
  const saveMembers = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/classes/{class_id}/students", {
          params: { path: { class_id: roster!.id } },
          body: { student_ids: memberIds },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      qc.invalidateQueries({ queryKey: ["class-members", roster?.id] });
      setRoster(null);
      toast("Matrícula actualizada.");
    },
  });
  function openCreate() {
    setEditing(null);
    form.reset({ name: "", academic_period: "", description: "" });
    setEditingOpen(true);
  }
  function openEdit(c: SchoolClass) {
    setEditing(c);
    form.reset({
      name: c.name,
      academic_period: c.academic_period,
      description: c.description,
    });
    setEditingOpen(true);
  }
  function openRoster(c: SchoolClass) {
    setRoster(c);
    setMemberIds([]);
  }
  useEffect(() => {
    if (currentMembers.data) setMemberIds(currentMembers.data.map((s) => s.id));
  }, [currentMembers.data]);
  return (
    <>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">VIDA ACADÉMICA</p>
        <div className="edu-heading-row">
          <div>
            <h1>Clases</h1>
            <p>
              Grupos pequeños para aprender, practicar y compartir hallazgos.
            </p>
          </div>
          {can("class.create") && (
            <Button onClick={openCreate}>
              <Plus size={15} /> Nueva clase
            </Button>
          )}
        </div>
      </header>
      <section className="edu-statline">
        <span>
          <BookOpen size={17} />
          <strong>{q.data?.total ?? "—"}</strong> espacios de aprendizaje
        </span>
        <label className="edu-search">
          <Search size={15} />
          <input
            placeholder="Buscar una clase"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </section>
      <section className="edu-class-grid">
        {q.data?.items.map((c, i) => (
          <article className="edu-class-card" key={c.id}>
            <div className="edu-class-index">
              SEMINARIO {String(i + 1).padStart(2, "0")}
              <span>↗</span>
            </div>
            <h2>{c.name}</h2>
            <p>{c.description || "Un espacio para aprender haciendo."}</p>
            <div className="edu-class-meta">
              <span>{c.academic_period || "Periodo por definir"}</span>
              <span>{c.student_count} estudiantes</span>
            </div>
            <div className="edu-class-teacher">
              {c.teacher_name ?? "Docente por asignar"}
              <div className="edu-class-actions">
                {can("class.update") && (
                  <button onClick={() => openEdit(c)}>Editar</button>
                )}
                {can("class.manage_students") && (
                  <button onClick={() => openRoster(c)}>Matrícula</button>
                )}
                {can("class.delete") && (
                  <button
                    onClick={() => {
                      if (c.student_count) {
                        toast(
                          "Retira primero a los estudiantes de esta clase.",
                        );
                        return;
                      }
                      if (window.confirm(`¿Eliminar la clase “${c.name}”?`))
                        remove.mutate(c);
                    }}
                  >
                    Eliminar
                  </button>
                )}
              </div>
            </div>
          </article>
        ))}
      </section>
      {!q.isLoading && !q.data?.items.length && (
        <EmptyState
          title="Tu campus empieza aquí"
          description="Crea la primera clase para reunir a estudiantes y docentes."
        />
      )}
      {editingOpen && (
        <div
          className="edu-modal-backdrop"
          onClick={() => setEditingOpen(false)}
        >
          <form
            className="edu-modal"
            onSubmit={form.handleSubmit((v) => save.mutate(v))}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="edu-modal-close"
              onClick={() => setEditingOpen(false)}
            >
              ×
            </button>
            <p className="page-eyebrow">VIDA ACADÉMICA</p>
            <h2>{editing ? "Editar clase." : "Crear una clase."}</h2>
            <label>
              Nombre
              <input className="ui-input" {...form.register("name")} />
              {form.formState.errors.name && (
                <small className="edu-error">
                  {form.formState.errors.name.message}
                </small>
              )}
            </label>
            <label>
              Periodo académico
              <input
                className="ui-input"
                placeholder="2026 · Segundo semestre"
                {...form.register("academic_period")}
              />
            </label>
            <label>
              Descripción
              <textarea
                className="ui-input"
                {...form.register("description")}
              />
            </label>
            {save.isError && <p className="edu-error">{save.error.message}</p>}
            <div className="edu-modal-actions">
              <Button
                variant="quiet"
                type="button"
                onClick={() => setEditingOpen(false)}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={save.isPending}>
                {editing ? "Guardar cambios" : "Crear clase"}
              </Button>
            </div>
          </form>
        </div>
      )}
      {roster && (
        <div className="edu-modal-backdrop" onClick={() => setRoster(null)}>
          <div className="edu-modal" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="edu-modal-close"
              onClick={() => setRoster(null)}
            >
              ×
            </button>
            <p className="page-eyebrow">MATRÍCULA</p>
            <h2>{roster.name}</h2>
            <p className="edu-modal-copy">
              Selecciona estudiantes para esta clase. Mantén Ctrl o ⌘ para
              elegir varios.
            </p>
            {students.isLoading || currentMembers.isLoading ? (
              <p>Cargando estudiantes…</p>
            ) : (
              <select
                className="ui-input edu-roster-select"
                multiple
                value={memberIds.map(String)}
                onChange={(e) =>
                  setMemberIds(
                    Array.from(e.target.selectedOptions, (o) =>
                      Number(o.value),
                    ),
                  )
                }
              >
                {students.data?.items.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.display_name} · @{s.username}
                  </option>
                ))}
              </select>
            )}
            {students.data?.items.length === 0 && (
              <p className="edu-hint">
                No hay estudiantes visibles para matricular en esta clase.
              </p>
            )}
            {saveMembers.isError && (
              <p className="edu-error">{saveMembers.error.message}</p>
            )}
            <div className="edu-modal-actions">
              <Button variant="quiet" onClick={() => setRoster(null)}>
                Cancelar
              </Button>
              <Button
                onClick={() => saveMembers.mutate()}
                disabled={saveMembers.isPending || students.isLoading}
              >
                {saveMembers.isPending ? "Guardando…" : "Guardar matrícula"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function ImportPage() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  async function choose(file?: File) {
    if (!file) return;
    if (file.size > 2_000_000) {
      toast("El archivo debe pesar menos de 2 MB.");
      return;
    }
    setBusy(true);
    setDone(false);
    try {
      const csv_content = await file.text();
      setPreview(
        (await unwrap(
          await api.POST("/api/v1/users/import/preview", {
            body: { filename: file.name, csv_content },
          }),
        )) as Preview,
      );
    } catch (e) {
      toast(e instanceof Error ? e.message : "No se pudo revisar el archivo.");
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!preview) return;
    setBusy(true);
    try {
      await unwrap(
        await api.POST("/api/v1/users/import/{job_id}/confirm", {
          params: { path: { job_id: preview.job_id } },
        }),
      );
      setDone(true);
      toast("Importación completada.");
    } catch (e) {
      toast(
        e instanceof Error ? e.message : "No se pudo completar la importación.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">INCORPORACIÓN DE ESTUDIANTES</p>
        <h1>Importar un curso.</h1>
        <p>
          Un archivo, una revisión cuidadosa y todo el grupo listo para empezar.
        </p>
      </header>
      <div className="edu-import-steps">
        <span className={!preview ? "current" : "complete"}>
          <i>{preview ? <Check size={13} /> : 1}</i> Selecciona
        </span>
        <b />
        <span className={preview && !done ? "current" : done ? "complete" : ""}>
          <i>{done ? <Check size={13} /> : 2}</i> Revisa
        </span>
        <b />
        <span className={done ? "complete" : ""}>
          <i>{done ? <Check size={13} /> : 3}</i> Confirma
        </span>
      </div>
      <section className="edu-panel edu-import-panel">
        <div className="edu-upload">
          <FileUp size={24} />
          <h2>
            {preview
              ? "Archivo revisado"
              : busy
                ? "Leyendo archivo…"
                : "Elige el listado del curso"}
          </h2>
          <p>CSV UTF-8 · máximo 2 MB · hasta 500 estudiantes</p>
          <label className="edu-file-button">
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => choose(e.target.files?.[0])}
            />
            Seleccionar archivo
          </label>
          <p className="edu-csv-hint">
            Columnas: username, nombre, apellido, curso, password_temporal,
            email
          </p>
        </div>
        {preview && (
          <>
            <div className="edu-preview-summary">
              <span>
                <strong>{preview.valid_count}</strong> filas listas
              </span>
              <span>
                <strong>{preview.error_count}</strong> necesitan revisión
              </span>
              <span>{preview.row_count} en total</span>
            </div>
            <div className="edu-table-scroll">
              <table className="edu-table">
                <thead>
                  <tr>
                    <th>FILA</th>
                    <th>ESTUDIANTE</th>
                    <th>CURSO</th>
                    <th>REVISIÓN</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.items.map((r) => (
                    <tr key={r.row_number}>
                      <td>{r.row_number}</td>
                      <td>
                        <strong>{r.display_name}</strong>
                        <small>@{r.username}</small>
                      </td>
                      <td>{r.course}</td>
                      <td>
                        {r.valid ? (
                          <span className="edu-valid">
                            <Check size={13} /> Lista
                          </span>
                        ) : (
                          <span className="edu-error">
                            {r.errors.join(" · ")}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="edu-import-confirm">
              <p>
                Las filas con errores se omitirán. Las personas importadas
                cambiarán su contraseña al entrar.
              </p>
              <Button
                onClick={confirm}
                disabled={busy || !preview.valid_count || done}
              >
                {done
                  ? "Importación completa"
                  : `Confirmar ${preview.valid_count} estudiantes`}{" "}
                <ArrowRight size={14} />
              </Button>
            </div>
          </>
        )}
      </section>
    </>
  );
}

export function ChangePasswordPage() {
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const form = useForm<{
    current_password: string;
    new_password: string;
    confirm: string;
  }>({
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });
  const mutation = useMutation({
    mutationFn: async (v: { current_password: string; new_password: string }) =>
      unwrap(await api.POST("/api/v1/auth/change-password", { body: v })),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["session"] });
      toast("Contraseña actualizada.");
    },
  });
  return (
    <>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">PRIMER INGRESO</p>
        <h1>Elige tu propia llave.</h1>
        <p>
          Por seguridad, actualiza la contraseña temporal antes de continuar.
        </p>
      </header>
      <form
        className="edu-panel edu-password-form"
        onSubmit={form.handleSubmit((v) => {
          setError("");
          if (v.new_password.length < 12) {
            setError("Usa al menos 12 caracteres.");
            return;
          }
          if (v.new_password !== v.confirm) {
            setError("Las contraseñas no coinciden.");
            return;
          }
          mutation.mutate({
            current_password: v.current_password,
            new_password: v.new_password,
          });
        })}
      >
        <label>
          Contraseña temporal
          <input
            className="ui-input"
            type="password"
            autoComplete="current-password"
            {...form.register("current_password", { required: true })}
          />
        </label>
        <label>
          Nueva contraseña
          <input
            className="ui-input"
            type="password"
            autoComplete="new-password"
            {...form.register("new_password", { required: true })}
          />
        </label>
        <label>
          Confirma la nueva contraseña
          <input
            className="ui-input"
            type="password"
            autoComplete="new-password"
            {...form.register("confirm", { required: true })}
          />
        </label>
        {(error || mutation.isError) && (
          <p className="edu-error">{error || mutation.error?.message}</p>
        )}
        <Button type="submit" disabled={mutation.isPending}>
          Actualizar contraseña <ArrowRight size={14} />
        </Button>
      </form>
    </>
  );
}
