import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { Moon, Plus, Sun } from "lucide-react";
import {
  Badge,
  Button,
  Checkbox,
  CommandPalette,
  DataTable,
  Dialog,
  Drawer,
  EmptyState,
  ErrorState,
  Input,
  Markdown,
  Select,
  Skeleton,
  Switch,
  Tab,
  TabList,
  TabPanel,
  Tabs,
  Textarea,
  Tooltip,
  toast,
} from "./ui";

type Row = { title: string; subject: string; state: string; points: number };
const sample: Row[] = [
  {
    title: "La pista en el encabezado",
    subject: "Análisis web",
    state: "Publicado",
    points: 150,
  },
  { title: "Ecos en la red", subject: "Redes", state: "Borrador", points: 200 },
  {
    title: "Un archivo fuera de lugar",
    subject: "Forense digital",
    state: "Completado",
    points: 100,
  },
];

export function DesignPage() {
  const [category, setCategory] = useState("web");
  const [checked, setChecked] = useState(true);
  const [enabled, setEnabled] = useState(true);
  const [palette, setPalette] = useState(false);
  const [dark, setDark] = useState(
    () => localStorage.getItem("cyberlab-theme") === "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  const columns: ColumnDef<Row, unknown>[] = [
    {
      accessorKey: "title",
      header: "Práctica",
      cell: (info) => (
        <strong className="demo-cell-title">{String(info.getValue())}</strong>
      ),
    },
    { accessorKey: "subject", header: "Área" },
    {
      accessorKey: "state",
      header: "Estado",
      cell: (info) => (
        <Badge
          status={
            info.getValue() === "Publicado"
              ? "live"
              : info.getValue() === "Completado"
                ? "done"
                : "draft"
          }
        >
          {String(info.getValue())}
        </Badge>
      ),
    },
    { accessorKey: "points", header: "Puntos" },
    {
      id: "select",
      header: "Marcar",
      enableSorting: false,
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(value)}
          label="Seleccionar"
        />
      ),
    },
  ];
  return (
    <main className="design-kitchen">
      <header className="design-top">
        <a href="/" className="design-wordmark">
          <span>CYBERLAB</span>
          <small>CUADERNOS DE CAMPO</small>
        </a>
        <span className="design-label">
          ATLAS DE COMPONENTES &nbsp; / &nbsp; V 0.2
        </span>
        <div className="design-top-actions">
          <button
            className="design-theme"
            onClick={() => {
              const next = !dark;
              setDark(next);
              localStorage.setItem("cyberlab-theme", next ? "dark" : "light");
            }}
            aria-label="Cambiar tema"
          >
            {dark ? <Sun size={14} /> : <Moon size={14} />}{" "}
            {dark ? "Claro" : "Oscuro"}
          </button>
          <a href="/login" className="design-back">
            Vista de acceso ↗
          </a>
        </div>
      </header>
      <section className="design-intro">
        <p className="page-eyebrow">
          FUNDACIÓN DE INTERFAZ &nbsp; · &nbsp; FASE 02
        </p>
        <h1>
          Una caja de herramientas
          <br />
          para <em>aprender mejor.</em>
        </h1>
        <p>
          Controles, estados y patrones compartidos del campus. Diseñados para
          acompañar el trabajo, no para competir con él.
        </p>
      </section>
      <section className="demo-section">
        <div className="demo-heading">
          <span>01</span>
          <div>
            <h2>Decisiones de identidad</h2>
            <p>
              Una paleta cálida, serif editorial y detalles de archivo técnico.
            </p>
          </div>
        </div>
        <div className="token-strip">
          {[
            ["Papel", "#f4f0e7"],
            ["Tinta", "#182729"],
            ["Señal", "#16e654"],
            ["Sombra de hoja", "#dbe0d6"],
            ["Línea", "#cbd0c7"],
          ].map(([name, color]) => (
            <div className="token-chip" key={name}>
              <i style={{ background: color }} />
              <span>
                {name}
                <small>{color}</small>
              </span>
            </div>
          ))}
        </div>
      </section>
      <section className="demo-section">
        <div className="demo-heading">
          <span>02</span>
          <div>
            <h2>Acción, selección y estado</h2>
            <p>
              Controles con estados legibles, teclado y texto acompañando el
              color.
            </p>
          </div>
        </div>
        <div className="demo-panel demo-controls">
          <div className="demo-control-row">
            <Button>
              Guardar nota <Plus size={14} />
            </Button>
            <Button variant="outline">Volver</Button>
            <Button variant="quiet">Secundaria</Button>
            <Button variant="danger">Archivar</Button>
            <Button disabled>Deshabilitado</Button>
            <Badge>En marcha</Badge>
            <Badge status="draft">Borrador</Badge>
            <Badge status="done">Resuelto</Badge>
            <Badge status="blocked">Bloqueado</Badge>
            <Badge status="danger">Requiere atención</Badge>
          </div>
          <div className="demo-fields">
            <label className="form-field">
              <span>Buscar una práctica</span>
              <Input placeholder="Ej. análisis de cabeceras" />
            </label>
            <label className="form-field">
              <span>Área de trabajo</span>
              <Select
                value={category}
                onValueChange={setCategory}
                options={[
                  { value: "web", label: "Análisis web" },
                  { value: "network", label: "Redes" },
                  { value: "forensics", label: "Forense digital" },
                ]}
              />
            </label>
            <label className="form-field">
              <span>Notas de campo</span>
              <Textarea rows={2} placeholder="Escribe una observación…" />
            </label>
          </div>
          <div className="demo-control-row">
            <Checkbox
              checked={checked}
              onCheckedChange={setChecked}
              label="Seleccionar esta fila"
            />
            <Switch
              checked={enabled}
              onCheckedChange={setEnabled}
              label="Visibilidad activa"
            />
            <Tooltip content="Información contextual, sin interrumpir el trabajo">
              <Button variant="outline">¿Qué significa esto?</Button>
            </Tooltip>
          </div>
        </div>
      </section>
      <section className="demo-section">
        <div className="demo-heading">
          <span>03</span>
          <div>
            <h2>Datos que se dejan explorar</h2>
            <p>
              Filtro, orden, paginación y selección de filas en una tabla
              compacta.
            </p>
          </div>
        </div>
        <DataTable
          columns={columns}
          data={sample}
          empty="Prueba con otra búsqueda."
        />
      </section>
      <section className="demo-section">
        <div className="demo-heading">
          <span>04</span>
          <div>
            <h2>Contenido y conversación</h2>
            <p>
              Superficies para enfocar una tarea, mostrar feedback y organizar
              información.
            </p>
          </div>
        </div>
        <div className="demo-panel demo-surface-grid">
          <Dialog
            trigger={<Button variant="outline">Abrir diálogo</Button>}
            title="Publicar práctica"
            description="El contenido se hará visible para las clases asignadas."
          >
            <div className="demo-dialog-actions">
              <Button variant="outline">Revisar</Button>
              <Button onClick={() => toast("La práctica quedó publicada.")}>
                Publicar ahora
              </Button>
            </div>
          </Dialog>
          <Drawer
            trigger={<Button variant="outline">Abrir panel lateral</Button>}
            title="Cuaderno de sesión"
          >
            <p className="muted-copy">
              Las notas y los indicadores de esta sesión aparecen aquí.
            </p>
            <Badge status="live">Sesión activa</Badge>
          </Drawer>
          <Tabs defaultValue="notes">
            <TabList>
              <Tab value="notes">Apuntes</Tab>
              <Tab value="files">Archivos</Tab>
              <Tab value="hints">Pistas</Tab>
            </TabList>
            <TabPanel value="notes">
              Resumen y observaciones del ejercicio.
            </TabPanel>
            <TabPanel value="files">Archivos adjuntos del reto.</TabPanel>
            <TabPanel value="hints">
              Ayudas disponibles para continuar.
            </TabPanel>
          </Tabs>
          <Button
            variant="quiet"
            onClick={() => toast("Cambios guardados en este cuaderno.")}
          >
            Mostrar aviso
          </Button>
        </div>
      </section>
      <section className="demo-section">
        <div className="demo-heading">
          <span>05</span>
          <div>
            <h2>Vacío, error y carga</h2>
            <p>Explican qué ocurre y cuál es el siguiente paso.</p>
          </div>
        </div>
        <div className="demo-state-grid">
          <EmptyState
            title="Todavía no hay apuntes"
            description="Empieza la práctica y registra lo que observes."
            action={<Button variant="outline">Abrir práctica</Button>}
          />
          <ErrorState
            title="No se pudo sincronizar"
            description="Tus notas siguen guardadas en este dispositivo."
            onRetry={() => toast("Intentando sincronizar…")}
          />
          <div className="loading-demo">
            <span>CARGANDO PRÁCTICAS</span>
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </div>
        </div>
      </section>
      <section className="demo-section">
        <div className="demo-heading">
          <span>06</span>
          <div>
            <h2>Texto de investigación</h2>
            <p>Markdown seguro, sin HTML crudo, con lectura y código.</p>
          </div>
        </div>
        <div className="demo-panel markdown-demo">
          <Markdown
            source={
              "## Observación\n\nEl servidor respondió con un encabezado inesperado.\n\n- Compara el valor con la petición inicial.\n- Anota la diferencia antes de cambiar de pista.\n\n`x-lab-route: archive-03`"
            }
          />
        </div>
      </section>
      <section className="demo-section">
        <div className="demo-heading">
          <span>07</span>
          <div>
            <h2>Navegación rápida</h2>
            <p>Abre con Ctrl/Cmd + K; filtra con teclado y sal con Escape.</p>
          </div>
        </div>
        <div className="demo-panel command-demo">
          <div>
            <strong>Ir a una sección</strong>
            <span>Paleta contextual de acciones</span>
          </div>
          <Button variant="outline" onClick={() => setPalette(true)}>
            Abrir paleta <kbd>⌘ K</kbd>
          </Button>
        </div>
      </section>
      <footer className="design-foot">
        <span>CYBERLAB &nbsp;·&nbsp; FASE 02</span>
        <span>
          CLARO / OSCURO &nbsp;·&nbsp; TECLADO &nbsp;·&nbsp; FOCO VISIBLE
        </span>
      </footer>
      <CommandPalette
        open={palette}
        onOpenChange={setPalette}
        items={[
          { label: "Mi espacio", action: () => setPalette(false) },
          { label: "Prácticas", action: () => setPalette(false) },
          { label: "Apuntes de clase", action: () => setPalette(false) },
        ]}
      />
    </main>
  );
}
