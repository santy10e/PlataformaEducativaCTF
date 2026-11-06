import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Lock, Snowflake, Trophy } from "lucide-react";
import { api, ApiError, unwrap } from "../api/client";
import { useAuth } from "./AuthProvider";
import {
  Badge,
  Button,
  Checkbox,
  EmptyState,
  ErrorState,
  Input,
  Select,
  Switch,
  toast,
} from "../components/ui";

type Setting = { key: string; value: unknown; description: string };
type Role = { id: number; name: string; is_system: boolean; permissions: string[] };
type AuditRow = {
  id: number;
  action: string;
  actor_user_id: number | null;
  target_type: string | null;
  target_id: string | null;
  meta: Record<string, unknown>;
  created_at: string;
};
type AuditPage = { items: AuditRow[]; total: number; page: number; page_size: number };
type BoardRow = { rank: number; display_name: string; score: number; grade: { grade: number; label: string } | null };
type Board = { scope: string; scope_id: string; frozen: boolean; items: BoardRow[] };
type Option = { value: string; label: string };

function failure(error: unknown) {
  toast(error instanceof ApiError ? error.message : "No se pudo guardar el cambio.");
}

function PageHeading({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <header className="workspace-page-heading">
      <p className="page-eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p>{copy}</p>
    </header>
  );
}

function SettingEditor({ setting, editable }: { setting: Setting; editable: boolean }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState(String(setting.value ?? ""));
  const save = useMutation({
    mutationFn: async (value: string | number | boolean) =>
      unwrap(await api.PUT("/api/v1/admin/settings/{key}", { params: { path: { key: setting.key } }, body: { value } })),
    onSuccess: async () => {
      toast("Ajuste guardado.");
      await qc.invalidateQueries({ queryKey: ["admin-settings"] });
    },
    onError: failure,
  });
  if (typeof setting.value === "boolean")
    return (
      <Switch
        checked={setting.value}
        disabled={!editable || save.isPending}
        onCheckedChange={(next) => save.mutate(next)}
        label={setting.value ? "Activado" : "Desactivado"}
      />
    );
  const numeric = typeof setting.value === "number";
  const changed = draft !== String(setting.value ?? "");
  return (
    <form
      className="admin-setting-form"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(numeric ? Number(draft) : draft.trim());
      }}
    >
      <Input
        aria-label={setting.description}
        type={numeric ? "number" : "text"}
        value={draft}
        disabled={!editable}
        onChange={(e) => setDraft(e.target.value)}
      />
      {editable && (
        <Button variant="outline" type="submit" disabled={!changed || save.isPending}>
          Guardar
        </Button>
      )}
    </form>
  );
}

export function SettingsPage() {
  const { can } = useAuth();
  const q = useQuery({
    queryKey: ["admin-settings"],
    queryFn: async () => (await unwrap(await api.GET("/api/v1/admin/settings"))) as Setting[],
  });
  const editable = can("settings.update");
  return (
    <>
      <PageHeading
        eyebrow="ADMINISTRACIÓN DEL CAMPUS"
        title="Configuración"
        copy="Reglas comunes a todas las clases: sesiones, intentos y visibilidad del marcador."
      />
      <section className="edu-panel">
        {q.isLoading ? (
          <div className="edu-empty">Cargando ajustes…</div>
        ) : q.isError ? (
          <ErrorState onRetry={() => q.refetch()} />
        ) : (
          <div className="admin-settings">
            {q.data?.map((setting) => (
              <div className="admin-setting-row" key={setting.key}>
                <div>
                  <strong>{setting.description}</strong>
                  <code>{setting.key}</code>
                </div>
                <SettingEditor key={String(setting.value)} setting={setting} editable={editable} />
              </div>
            ))}
          </div>
        )}
        {!editable && <p className="edu-hint admin-note">Tu rol puede consultar estos ajustes, pero no modificarlos.</p>}
      </section>
    </>
  );
}

const permissionGroups: Record<string, string> = {
  audit: "Bitácora",
  category: "Categorías",
  challenge: "Retos",
  class: "Clases",
  difficulty: "Dificultades",
  event: "Eventos",
  import: "Importación de estudiantes",
  role: "Roles",
  scoreboard: "Marcador",
  settings: "Configuración",
  user: "Personas",
};

function RoleEditor({ role, catalogue, editable }: { role: Role; catalogue: string[]; editable: boolean }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState(() => new Set(role.permissions));
  const locked = role.name === "ADMIN" || !editable;
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/admin/roles/{role_id}", {
          params: { path: { role_id: role.id } },
          body: { name: role.name, permissions: [...selected].sort() },
        }),
      ),
    onSuccess: async () => {
      toast(`Permisos de ${role.name} actualizados.`);
      await qc.invalidateQueries({ queryKey: ["admin-roles"] });
    },
    onError: failure,
  });
  const grouped = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const code of catalogue) {
      const group = code.split(".")[0];
      groups.set(group, [...(groups.get(group) ?? []), code]);
    }
    return [...groups.entries()];
  }, [catalogue]);
  const dirty = selected.size !== role.permissions.length || role.permissions.some((code) => !selected.has(code));
  return (
    <article className="admin-role">
      <header>
        <div>
          <h2>{role.name}</h2>
          <small>
            {selected.size} de {catalogue.length} permisos
          </small>
        </div>
        {role.name === "ADMIN" ? (
          <Badge status="blocked">
            <Lock size={11} /> Protegido
          </Badge>
        ) : (
          <Badge status={role.is_system ? "done" : "draft"}>{role.is_system ? "Rol del sistema" : "Personalizado"}</Badge>
        )}
      </header>
      {role.name === "ADMIN" && <p className="admin-role-note">El rol administrador conserva siempre todos los permisos para que nadie pierda el control de la plataforma.</p>}
      <div className="admin-permission-grid">
        {grouped.map(([group, codes]) => (
          <fieldset key={group}>
            <legend>{permissionGroups[group] ?? group}</legend>
            {codes.map((code) => (
              <Checkbox
                key={code}
                label={code}
                checked={selected.has(code)}
                disabled={locked}
                onCheckedChange={(on) =>
                  setSelected((current) => {
                    const next = new Set(current);
                    if (on) next.add(code);
                    else next.delete(code);
                    return next;
                  })
                }
              />
            ))}
          </fieldset>
        ))}
      </div>
      {!locked && (
        <div className="admin-role-actions">
          <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
            Guardar permisos
          </Button>
          {dirty && (
            <Button variant="quiet" onClick={() => setSelected(new Set(role.permissions))}>
              Descartar
            </Button>
          )}
        </div>
      )}
    </article>
  );
}

export function RolesPage() {
  const { can } = useAuth();
  const q = useQuery({
    queryKey: ["admin-roles"],
    queryFn: async () => (await unwrap(await api.GET("/api/v1/admin/roles"))) as Role[],
  });
  const catalogue = useMemo(
    () => [...new Set((q.data ?? []).flatMap((role) => role.permissions))].sort(),
    [q.data],
  );
  return (
    <>
      <PageHeading
        eyebrow="ACCESO AL CAMPUS"
        title="Roles"
        copy="Qué puede hacer cada perfil. Los cambios se aplican en la siguiente acción de cada persona."
      />
      {q.isLoading ? (
        <div className="edu-empty">Cargando roles…</div>
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : (
        <section className="admin-roles">
          {q.data?.map((role) => (
            <RoleEditor key={`${role.id}-${role.permissions.join()}`} role={role} catalogue={catalogue} editable={can("role.update")} />
          ))}
        </section>
      )}
    </>
  );
}

function describeTarget(row: AuditRow) {
  if (!row.target_type) return "—";
  return row.target_id ? `${row.target_type} · ${row.target_id}` : row.target_type;
}

export function AuditPage() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [applied, setApplied] = useState("");
  const q = useQuery({
    queryKey: ["admin-audit", page, applied],
    queryFn: async () =>
      (await unwrap(
        await api.GET("/api/v1/admin/audit", { params: { query: { page, page_size: 50, action: applied || undefined } } }),
      )) as AuditPage,
  });
  const pages = q.data ? Math.max(1, Math.ceil(q.data.total / q.data.page_size)) : 1;
  return (
    <>
      <PageHeading
        eyebrow="REGISTRO DEL SISTEMA"
        title="Bitácora"
        copy="Inicios de sesión, cambios de cuentas, retos, calificaciones y ajustes, del más reciente al más antiguo."
      />
      <section className="edu-panel">
        <form
          className="edu-toolbar"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setApplied(action.trim().toUpperCase());
          }}
        >
          <Input
            aria-label="Filtrar por acción"
            placeholder="Acción exacta, por ejemplo LOGIN_FAILED"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          />
          <div className="edu-actions">
            <Button variant="outline" type="submit">Filtrar</Button>
            {applied && (
              <Button variant="quiet" type="button" onClick={() => { setAction(""); setApplied(""); setPage(1); }}>
                Quitar filtro
              </Button>
            )}
          </div>
        </form>
        {q.isLoading ? (
          <div className="edu-empty">Cargando registros…</div>
        ) : q.isError ? (
          <ErrorState onRetry={() => q.refetch()} />
        ) : !q.data?.items.length ? (
          <EmptyState title="Sin registros" description={applied ? `No hay eventos ${applied}.` : "Todavía no se registró actividad."} />
        ) : (
          <>
            <div className="edu-table-scroll">
              <table className="edu-table">
                <thead>
                  <tr>
                    <th>FECHA</th>
                    <th>ACCIÓN</th>
                    <th>USUARIO</th>
                    <th>OBJETO</th>
                    <th>DETALLE</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.items.map((row) => (
                    <tr key={row.id}>
                      <td>{new Date(row.created_at.endsWith("Z") ? row.created_at : `${row.created_at}Z`).toLocaleString()}</td>
                      <td><code>{row.action}</code></td>
                      <td>{row.actor_user_id ? `#${row.actor_user_id}` : "Sistema / anónimo"}</td>
                      <td>{describeTarget(row)}</td>
                      <td><small className="admin-meta">{Object.keys(row.meta ?? {}).length ? JSON.stringify(row.meta) : "—"}</small></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="admin-pager">
              <Button variant="quiet" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Página anterior">
                <ChevronLeft size={15} />
              </Button>
              <span>
                Página {page} de {pages} · {q.data.total} registros
              </span>
              <Button variant="quiet" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Página siguiente">
                <ChevronRight size={15} />
              </Button>
            </div>
          </>
        )}
      </section>
    </>
  );
}

type Scope = "GLOBAL" | "CLASS" | "EVENT";

export function StaffScoreboardPage() {
  const { user, can } = useAuth();
  const qc = useQueryClient();
  const isAdmin = user?.roles.includes("ADMIN") === true;
  const [scope, setScope] = useState<Scope>(isAdmin ? "GLOBAL" : "CLASS");
  const [scopeId, setScopeId] = useState("");
  const classes = useQuery({
    queryKey: ["scoreboard-classes"],
    queryFn: async () =>
      ((await unwrap(await api.GET("/api/v1/classes", { params: { query: { page: 1, page_size: 100 } } }))) as {
        items: { id: number; name: string; academic_period: string }[];
      }).items.map((c): Option => ({ value: String(c.id), label: c.academic_period ? `${c.name} · ${c.academic_period}` : c.name })),
  });
  const events = useQuery({
    queryKey: ["scoreboard-events"],
    enabled: can("event.manage"),
    queryFn: async () =>
      ((await unwrap(await api.GET("/api/v1/ctf/events", { params: { query: { page: 1, page_size: 100 } } }))) as {
        items: { public_id: string; name: string }[];
      }).items.map((e): Option => ({ value: e.public_id, label: e.name })),
  });
  const ready = scope === "GLOBAL" || scopeId !== "";
  const board = useQuery({
    queryKey: ["staff-scoreboard", scope, scopeId],
    enabled: ready,
    refetchInterval: 60_000,
    queryFn: async () =>
      (await unwrap(
        await api.GET("/api/v1/ctf/scoreboard", { params: { query: { scope, scope_id: scope === "GLOBAL" ? "0" : scopeId } } }),
      )) as Board,
  });
  const freeze = useMutation({
    mutationFn: async (frozen: boolean) =>
      unwrap(await api.POST("/api/v1/ctf/scoreboard/freeze", { body: { scope, scope_id: scope === "GLOBAL" ? "0" : scopeId, frozen } })),
    onSuccess: async (_data, frozen) => {
      toast(frozen ? "Marcador congelado: los estudiantes verán esta foto hasta que lo reactives." : "Marcador en vivo de nuevo.");
      await qc.invalidateQueries({ queryKey: ["staff-scoreboard"] });
    },
    onError: failure,
  });
  const choose = (next: Scope) => {
    setScope(next);
    setScopeId("");
  };
  const options = scope === "CLASS" ? classes.data ?? [] : events.data ?? [];
  const top = board.data?.items[0]?.score ?? 0;
  const canFreeze = can("scoreboard.manage") && (scope !== "GLOBAL" || isAdmin) && ready && board.isSuccess;
  return (
    <>
      <PageHeading
        eyebrow="SEGUIMIENTO DE RESULTADOS"
        title="Marcador"
        copy="Las mismas posiciones que ven tus estudiantes, por clase o por evento."
      />
      <section className="edu-panel">
        <div className="edu-toolbar admin-scope-bar">
          <div className="edu-filters" role="group" aria-label="Alcance del marcador">
            {isAdmin && (
              <button className={scope === "GLOBAL" ? "selected" : ""} onClick={() => choose("GLOBAL")}>
                Todo el campus
              </button>
            )}
            <button className={scope === "CLASS" ? "selected" : ""} onClick={() => choose("CLASS")}>
              Por clase
            </button>
            <button className={scope === "EVENT" ? "selected" : ""} onClick={() => choose("EVENT")}>
              Por evento
            </button>
          </div>
          {scope !== "GLOBAL" && (
            <div className="admin-scope-select">
              <Select
                value={scopeId || undefined}
                onValueChange={setScopeId}
                options={options}
                placeholder={scope === "CLASS" ? "Elige una clase" : "Elige un evento"}
              />
            </div>
          )}
          {canFreeze && (
            <Switch
              checked={board.data?.frozen === true}
              disabled={freeze.isPending}
              onCheckedChange={(next) => freeze.mutate(next)}
              label="Congelar"
            />
          )}
        </div>
        {board.data?.frozen && (
          <p className="edu-hint admin-note">
            <Snowflake size={13} /> Congelado: se muestra la foto guardada, no la puntuación en vivo.
          </p>
        )}
        {!ready ? (
          <EmptyState title="Elige qué marcador ver" description={options.length ? "Selecciona una clase o un evento." : "Aún no tienes clases o eventos asignados."} />
        ) : board.isLoading ? (
          <div className="edu-empty">Calculando posiciones…</div>
        ) : board.isError ? (
          <ErrorState
            description={board.error instanceof ApiError ? board.error.message : "No se pudo cargar el marcador."}
            onRetry={() => board.refetch()}
          />
        ) : !board.data?.items.length ? (
          <EmptyState title="Aún no hay puntuaciones" description="Las posiciones aparecen cuando alguien resuelve o usa una pista." />
        ) : (
          <div className="edu-table-scroll">
            <table className="edu-table admin-board">
              <thead>
                <tr>
                  <th>POS.</th>
                  <th>ESTUDIANTE</th>
                  <th>XP</th>
                  <th>NOTA</th>
                </tr>
              </thead>
              <tbody>
                {board.data.items.map((row) => (
                  <tr key={`${row.rank}-${row.display_name}`}>
                    <td>
                      {String(row.rank).padStart(2, "0")} {row.rank <= 3 && <Trophy size={13} aria-label="Podio" />}
                    </td>
                    <td>
                      <strong>{row.display_name}</strong>
                      <span className="admin-bar" style={{ width: `${top > 0 ? Math.max(2, (row.score / top) * 100) : 2}%` }} />
                    </td>
                    <td>{row.score} XP</td>
                    <td>{row.grade ? `${row.grade.grade} · ${row.grade.label}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

const studentHelp = [
  ["Entra con tu usuario", "Usa las credenciales que te dio tu docente. La primera vez la plataforma te pedirá una contraseña nueva y personal."],
  ["Abre un evento", "En «Eventos» aparecen las competencias activas de tus clases. Lee las reglas y la fecha de cierre antes de empezar."],
  ["Inicia un reto", "Al pulsar «Iniciar reto» empieza a contar tu tiempo. Si un reto está bloqueado, resuelve primero los retos que indica."],
  ["Pide pistas con cuidado", "Las pistas se desbloquean en orden y cada una muestra su costo en XP antes de revelarse."],
  ["Envía la bandera", "Escribe la bandera exacta y pulsa «Enviar respuesta». La plataforma te dirá si es correcta y cuántos intentos te quedan."],
  ["Revisa tu avance", "«Mi espacio» resume tu XP, tiempos e historial; «Marcador» muestra las posiciones."],
];
const teacherHelp = [
  ["Prepara el evento", "En «Diseñar CTF» crea un evento y asígnalo a una o varias de tus clases. Queda en borrador hasta que lo publiques."],
  ["Crea retos publicables", "Cada reto necesita al menos una bandera antes de publicarse. Añade pistas ordenadas, archivos y prerrequisitos."],
  ["Importa paquetes", "«Importar retos» valida un ZIP antes de crear nada; todo lo importado llega como borrador."],
  ["Acompaña la clase", "«Seguimiento docente» muestra avances, intentos, inactividad y el aula en vivo; desde ahí publicas avisos y exportas CSV, XLSX o PDF."],
  ["Gestiona el marcador", "En «Marcador» eliges clase o evento y puedes congelarlo para conservar una foto estable de los resultados."],
  ["Organiza a tus estudiantes", "En «Clases» y «Personas» ves solo tus grupos. Para incorporar estudiantes nuevos usa el alta o la importación CSV."],
];
const adminHelp = [
  ["Cuentas y clases", "Crea docentes, asigna clases y matricula estudiantes. Solo la administración puede mover estudiantes entre clases de distintos docentes."],
  ["Reglas del campus", "«Configuración» define la duración de las sesiones, el máximo de intentos, el límite de envíos por minuto y si el marcador es visible."],
  ["Permisos", "«Roles» ajusta qué pueden hacer docentes y estudiantes. El rol administrador está protegido."],
  ["Trazabilidad", "«Bitácora» registra accesos, cambios de cuentas, retos y calificaciones."],
  ["Operación", "Las copias de seguridad, restauraciones y actualizaciones se describen en la guía de instalación del servidor."],
];

export function HelpPage() {
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const sections: [string, string[][]][] = [];
  if (roles.includes("STUDENT")) sections.push(["Para estudiantes", studentHelp]);
  if (roles.includes("INSTRUCTOR") || roles.includes("ADMIN")) sections.push(["Para docentes", teacherHelp]);
  if (roles.includes("ADMIN")) sections.push(["Para administración", adminHelp]);
  return (
    <>
      <PageHeading eyebrow="CÓMO ORIENTARTE" title="Ayuda" copy="Los pasos esenciales de tu perfil en Cyberlab." />
      {sections.map(([title, items]) => (
        <section className="edu-panel admin-help" key={title}>
          <h2>{title}</h2>
          <ol>
            {items.map(([heading, copy]) => (
              <li key={heading}>
                <strong>{heading}</strong>
                <p>{copy}</p>
              </li>
            ))}
          </ol>
        </section>
      ))}
      <section className="edu-panel admin-help">
        <h2>Uso responsable</h2>
        <p>Trabaja solo dentro de los retos y objetivos autorizados por tu docente. No ataques la infraestructura que aloja la plataforma ni compartas soluciones de actividades evaluadas sin permiso.</p>
      </section>
    </>
  );
}
