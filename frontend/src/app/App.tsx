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
import { AuditPage, HelpPage, RolesPage, SettingsPage, StaffScoreboardPage } from "./administration";
import { CurriculumStudioPage } from "../features/curriculum/CurriculumStudio";
import { LearnCoursePage, LearnHomePage, LearnLessonPage } from "../features/curriculum/LearnPages";

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
  const isStudent = user?.roles.includes("STUDENT") === true;
  const visibleRoutes = routes.filter(
    (route) =>
      (!route.permission || can(route.permission)) &&
      (route.audience !== "student" || isStudent),
  );
  // Nested pages (a lesson inside /learn, for example) belong to their closest section in the breadcrumb.
  const current = routes
    .filter((route) => location.pathname === route.path || location.pathname.startsWith(`${route.path}/`))
    .sort((a, b) => b.path.length - a.path.length)[0];
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
            {window.location.protocol === "https:" ? "SESIÓN CIFRADA" : "SESIÓN ACTIVA"} <i />
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

function StaffWorkspace() {
  const { user, can } = useAuth();
  const navigate = useNavigate();
  const shortcuts = routes.filter(
    (route) =>
      route.path !== "/workspace" &&
      route.path !== "/help" &&
      route.audience !== "student" &&
      (!route.permission || can(route.permission)),
  );
  const primary = can("event.manage")
    ? { path: "/teaching/ctf", label: "Diseñar una práctica" }
    : { path: "/users", label: "Ver el directorio" };
  return (
    <>
      <div className="workspace-edition">
        <span>
          CUADERNO DE TRABAJO &nbsp; / &nbsp; {user?.roles?.join(" · ")}
        </span>
        <span>{new Date().toLocaleDateString()}</span>
      </div>
      <section className="workspace-welcome">
        <div>
          <p className="page-eyebrow">TU ESPACIO DOCENTE</p>
          <h1>Hola, {user?.display_name ?? user?.username}.</h1>
          <p>Prepara prácticas, acompaña a tus clases y revisa sus avances.</p>
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
            Diseña un reto, asígnalo a una clase y observa cómo cada estudiante
            avanza a su propio ritmo.
          </p>
          <Button onClick={() => navigate(primary.path)}>
            {primary.label} <span aria-hidden="true">↗</span>
          </Button>
          <div className="feature-illustration">
            <div className="feature-orbit feature-orbit-a" />
            <div className="feature-orbit feature-orbit-b" />
            <span>?</span>
          </div>
        </article>
        <aside className="workspace-side-note">
          <div className="side-note-top">
            <span>ACCESOS DE TU PERFIL</span>
            <Badge status="live">En marcha</Badge>
          </div>
          <nav className="workspace-shortcuts" aria-label="Accesos rápidos">
            {shortcuts.map((route) => {
              const Icon = route.icon;
              return (
                <Link key={route.path} to={route.path}>
                  <Icon size={15} />
                  <span>
                    <strong>{route.label}</strong>
                    <small>{route.description}</small>
                  </span>
                </Link>
              );
            })}
          </nav>
        </aside>
      </div>
    </>
  );
}

function WorkspaceHome() {
  const { user } = useAuth();
  return user?.roles.includes("STUDENT") ? <StudentDashboard /> : <StaffWorkspace />;
}

/** Learners and staff share these paths; staff see the management view of the same data. */
function SharedRoute({ path }: { path: string }) {
  const { user } = useAuth();
  if (user?.roles.includes("STUDENT")) {
    if (path === "/learn") return <LearnHomePage />;
    return path === "/scoreboard" ? <StudentScoreboardPage /> : <StudentEventsPage />;
  }
  if (path === "/scoreboard") return <StaffScoreboardPage />;
  return <Navigate to={path === "/learn" ? "/teaching/curriculum" : "/teaching/ctf"} replace />;
}

const pages: Record<string, ReactNode> = {
  "/learn": <SharedRoute path="/learn" />,
  "/teaching/curriculum": <CurriculumStudioPage />,
  "/users": <PeoplePage />,
  "/classes": <ClassManagementPage />,
  "/teaching/ctf": <CtfManagementPage />,
  "/teaching/analytics": <TeachingAnalyticsPage />,
  "/teaching/importer": <ChallengeImporterPage />,
  "/events": <SharedRoute path="/events" />,
  "/challenges": <SharedRoute path="/challenges" />,
  "/scoreboard": <SharedRoute path="/scoreboard" />,
  "/settings": <SettingsPage />,
  "/roles": <RolesPage />,
  "/audit": <AuditPage />,
  "/help": <HelpPage />,
};

function Workspaces() {
  return <RoutesView />;
}
function RoutesView() {
  return (
    <Routes>
      <Route element={<Guard />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/workspace" replace />} />
          <Route path="workspace" element={<WorkspaceHome />} />
          {routes
            .filter((route) => route.path !== "/workspace")
            .map((route) => (
              <Route
                key={route.path}
                path={route.path.slice(1)}
                element={<Guard permission={route.permission} />}
              >
                <Route index element={pages[route.path] ?? <NotFoundPage />} />
              </Route>
            ))}
          <Route path="learn/courses/:publicId" element={<Guard permission="course.view" />}>
            <Route index element={<LearnCoursePage />} />
          </Route>
          <Route path="learn/lessons/:publicId" element={<Guard permission="course.view" />}>
            <Route index element={<LearnLessonPage />} />
          </Route>
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
