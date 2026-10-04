import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { BookOpen, Command, LogOut, Moon, Search, Sun } from "lucide-react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./AuthProvider";
import { routes } from "./routes";
import { LoginPage, NotFoundPage, ForbiddenPage } from "./pages";
import {
  Badge,
  Button,
  CommandPalette,
  EmptyState,
  Skeleton,
  ToastProvider,
  toast,
} from "../components/ui";
import {
  ChangePasswordPage,
  ClassManagementPage,
  ImportPage,
  PeoplePage,
} from "./education";
import { CtfManagementPage } from "./ctf-management";
import { TeachingAnalyticsPage } from "./teaching-analytics";
import { ChallengeImporterPage } from "./challenge-importer";
import { ChallengePlayPage, StudentDashboard, StudentEventsPage, StudentScoreboardPage } from "./student";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});
const Fieldbook = lazy(() =>
  import("../Fieldbook").then((module) => ({ default: module.Fieldbook })),
);
const DesignPage = lazy(() =>
  import("../components/DesignPage").then((module) => ({
    default: module.DesignPage,
  })),
);

function Guard({ permission }: { permission?: string }) {
  const { loading, user, can } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <div className="workspace-loading">
        <Skeleton className="loading-rule" />
        <Skeleton className="loading-title" />
        <Skeleton className="loading-block" />
      </div>
    );
  if (!user)
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.must_change_password && location.pathname !== "/change-password")
    return <Navigate to="/change-password" replace />;
  if (permission && !can(permission)) return <Navigate to="/403" replace />;
  return <Outlet />;
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="login-loading">
        <Skeleton className="loading-block" />
      </div>
    );
  return user ? <Navigate to="/workspace" replace /> : <>{children}</>;
}

function ThemeButton() {
  const [dark, setDark] = useState(
    () => localStorage.getItem("cyberlab-theme") === "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  function toggle() {
    const next = dark ? "light" : "dark";
    setDark(!dark);
    document.documentElement.dataset.theme = next;
    localStorage.setItem("cyberlab-theme", next);
  }
  return (
    <Button
      variant="quiet"
      className="top-icon-button"
      aria-label={`Cambiar a tema ${dark ? "claro" : "oscuro"}`}
      onClick={toggle}
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </Button>
  );
}

function AppShell() {
  const { user, can, logout } = useAuth();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const visibleRoutes = routes.filter(
    (route) => !route.permission || can(route.permission),
  );
  const current = routes.find((route) => route.path === location.pathname);
  const commandItems = useMemo(
    () =>
      visibleRoutes.map((route) => ({
        label: route.label,
        hint: route.path,
        action: () => navigate(route.path),
      })),
    [navigate, visibleRoutes],
  );

  async function signOut() {
    try {
      await logout();
    } catch {
      toast("La sesión ya no está activa.");
    }
    navigate("/login", { replace: true });
  }

  return (
    <div className="workspace-shell">
      <aside className="workspace-rail">
        <Link
          to="/workspace"
          className="workspace-mark"
          aria-label="Cyberlab, mi espacio"
        >
          <BookOpen size={18} />
        </Link>
        <span className="rail-rule" />
        <nav className="workspace-nav" aria-label="Navegación principal">
          {visibleRoutes.map((route) => {
            const Icon = route.icon;
            return (
              <Link
                key={route.path}
                to={route.path}
                aria-label={route.label}
                title={route.label}
                className={
                  location.pathname === route.path ? "workspace-nav-active" : ""
                }
              >
                <Icon size={17} />
                <span>{route.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="rail-bottom">
          <Badge status="done">{user?.roles[0] ?? "Campus"}</Badge>
          <button
            className="rail-account"
            onClick={signOut}
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
          >
            <span>{user?.display_name?.slice(0, 1) ?? "C"}</span>
            <LogOut size={14} />
          </button>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-topbar">
          <div className="workspace-breadcrumb">
            <Link to="/workspace">Cyberlab</Link>
            <span>/</span>
            <strong>{current?.label ?? "Mi espacio"}</strong>
          </div>
          <div className="workspace-top-actions">
            <Button
              variant="outline"
              className="palette-launch"
              onClick={() => setPaletteOpen(true)}
            >
              <Search size={14} />
              <span>Buscar en el campus</span>
              <kbd>
                <Command size={10} /> K
              </kbd>
            </Button>
            <ThemeButton />
            <Button variant="quiet" onClick={signOut} className="signout-top">
              <LogOut size={15} />
              <span>Salir</span>
            </Button>
          </div>
        </header>
        <main className="workspace-content">
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>CYBERLAB &nbsp;·&nbsp; CUADERNO DE APRENDIZAJE</span>
          <span>
            SESIÓN CIFRADA <i />
          </span>
        </footer>
      </div>
      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        items={commandItems}
      />
    </div>
  );
}

function WorkspacePage({
  title,
  description,
  phase,
}: {
  title: string;
  description: string;
  phase: number;
}) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  if (pathname === "/workspace" && user?.roles.includes("STUDENT")) return <StudentDashboard />;
  if (pathname === "/workspace")
    return (
      <>
        <div className="workspace-edition">
          <span>
            CUADERNO PERSONAL &nbsp; / &nbsp; {user?.roles?.join(" · ")}
          </span>
          <span>01 — 12</span>
        </div>
        <section className="workspace-welcome">
          <div>
            <p className="page-eyebrow">TU PRÓXIMO DESCUBRIMIENTO</p>
            <h1>
              Hola, {user?.display_name?.split(" ")[0] ?? user?.username}.
            </h1>
            <p>
              El laboratorio está listo. Elige una práctica y empieza a
              investigar.
            </p>
          </div>
          <div className="welcome-seal">
            <BookOpen size={25} />
            <span>
              APRENDER
              <br />
              HACIENDO
            </span>
          </div>
        </section>
        <div className="workspace-content-grid">
          <article className="workspace-feature">
            <span className="feature-number">01 / CUADERNO ABIERTO</span>
            <h2>
              Todo comienza
              <br />
              con una pregunta.
            </h2>
            <p>
              Explora las señales, toma notas y avanza a tu propio ritmo. Cada
              reto te acerca a una nueva forma de entender la seguridad digital.
            </p>
            <Button
              onClick={() =>
                toast("El catálogo de prácticas llegará en la Fase 4.")
              }
            >
              Explorar prácticas <span aria-hidden="true">↗</span>
            </Button>
            <div className="feature-illustration">
              <div className="feature-orbit feature-orbit-a" />
              <div className="feature-orbit feature-orbit-b" />
              <span>?</span>
            </div>
          </article>
          <aside className="workspace-side-note">
            <div className="side-note-top">
              <span>ESTADO DEL RECORRIDO</span>
              <Badge status="live">En marcha</Badge>
            </div>
            <h3>Tu espacio de aprendizaje</h3>
            <p>
              Has iniciado sesión como {user?.username}. Aquí aparecerán tus
              retos, avances y actividad de clase cuando se habiliten en las
              siguientes fases.
            </p>
            <div className="note-divider" />
            <span className="next-step-label">SIGUIENTE EN EL PROYECTO</span>
            <strong>Perfiles y clases</strong>
            <small>
              FASE {phase + 1} &nbsp;·&nbsp; ADMINISTRACIÓN EDUCATIVA
            </small>
          </aside>
        </div>
        <section className="permission-note">
          <span>PERMISOS DE ESTA SESIÓN</span>
          <p>
            {user?.permissions?.length
              ? user.permissions.map((permission) => (
                  <code key={permission}>{permission}</code>
                ))
              : "Sin permisos asignados."}
          </p>
        </section>
      </>
    );
  return (
    <>
      <div className="workspace-edition">
        <span>CYBERLAB &nbsp; / &nbsp; ESPACIO DE TRABAJO</span>
        <span>FASE {phase}</span>
      </div>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">ÁREA DE APRENDIZAJE</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </header>
      <div className="planned-feature">
        <EmptyState
          title="Esta sección se está preparando"
          description={`Su implementación corresponde a la Fase ${phase} del plan de Cyberlab.`}
        />
      </div>
    </>
  );
}

function Workspaces() {
  return <RoutesView />;
}
function StudentOrWorkspace({ path, title, description, phase }: { path: string; title: string; description: string; phase: number }) {
  const { user } = useAuth();
  if (user?.roles.includes("STUDENT")) return path === "/scoreboard" ? <StudentScoreboardPage /> : <StudentEventsPage />;
  return <WorkspacePage title={title} description={description} phase={phase} />;
}
function RoutesView() {
  return (
    <Routes>
      <Route element={<Guard />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/workspace" replace />} />
          <Route
            path="workspace"
            element={
              <WorkspacePage
                title="Mi espacio"
                description="Tu cuaderno personal."
                phase={2}
              />
            }
          />
          {routes
            .filter((route) => route.path !== "/workspace")
            .map((route) => (
              <Route
                key={route.path}
                path={route.path.slice(1)}
                element={<Guard permission={route.permission} />}
              >
                <Route
                  index
                  element={
                    route.path === "/users" ? (
                      <PeoplePage />
                    ) : route.path === "/classes" ? (
                      <ClassManagementPage />
                    ) : route.path === "/teaching/ctf" ? (
                      <CtfManagementPage />
                    ) : route.path === "/teaching/analytics" ? (
                      <TeachingAnalyticsPage />
                    ) : route.path === "/teaching/importer" ? (
                      <ChallengeImporterPage />
                    ) : route.path === "/events" || route.path === "/challenges" || route.path === "/scoreboard" ? (
                      <StudentOrWorkspace path={route.path} title={route.label} description={route.description} phase={route.phase} />
                    ) : (
                      <WorkspacePage
                        title={route.label}
                        description={route.description}
                        phase={route.phase}
                      />
                    )
                  }
                />
              </Route>
            ))}
          <Route path="import" element={<Guard permission="import.preview" />}>
            <Route index element={<ImportPage />} />
          </Route>
          <Route path="change-password" element={<Guard />}>
            <Route index element={<ChangePasswordPage />} />
          </Route>
          <Route path="study/events/:eventPublicId/challenges/:challengePublicId" element={<Guard permission="challenge.submit" />}>
            <Route index element={<ChallengePlayPage />} />
          </Route>
          <Route path="403" element={<ForbiddenPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Fieldbook />} />
      <Route
        path="/login"
        element={
          <PublicOnly>
            <LoginPage />
          </PublicOnly>
        }
      />
      <Route path="/design" element={<DesignPage />} />
      <Route path="/403" element={<ForbiddenPage />} />
      <Route path="/404" element={<NotFoundPage />} />
      <Route path="/*" element={<Workspaces />} />
    </Routes>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Suspense
              fallback={
                <div className="workspace-loading">
                  <Skeleton className="loading-block" />
                </div>
              }
            >
              <AppRoutes />
            </Suspense>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
