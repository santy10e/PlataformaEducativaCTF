import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookCopy, BookOpen, CheckCircle2, Eye, FilePen, Layers, Lock, Plus, Save, Trash2 } from "lucide-react";
import { api, ApiError, unwrap } from "../../api/client";
import { Badge, Button, Checkbox, EmptyState, ErrorState, Input, Markdown, Select, Textarea, toast } from "../../components/ui";
import { ActivityEditor } from "./ActivityEditor";
import { kindLabel, publishLabel, type CourseProgress, type ReviewRow, type StaffActivity, type StaffCourse, type StaffLesson, type StaffModule, type Status } from "./types";
import "./curriculum.css";

type Selection =
  | { kind: "course" }
  | { kind: "module"; module: StaffModule | null }
  | { kind: "lesson"; moduleId: number; lesson: StaffLesson | null }
  | { kind: "activity"; lessonId: number; activity: StaffActivity | null };

function failure(error: unknown) {
  toast(error instanceof ApiError ? error.message : "No se pudo guardar.");
}

const statusOptions = (["DRAFT", "PUBLISHED"] as Status[]).map((s) => ({ value: s, label: publishLabel[s] }));

export function CurriculumStudioPage() {
  const qc = useQueryClient();
  const [courseId, setCourseId] = useState<number | null>(null);
  const [tab, setTab] = useState<"content" | "progress" | "reviews">("content");
  const courses = useQuery({ queryKey: ["cur-courses"], queryFn: async () => (await unwrap(await api.GET("/api/v1/curriculum/courses"))) as StaffCourse[] });
  const create = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/curriculum/courses", { body: { title: "Nuevo curso", description_markdown: "", status: "DRAFT" } })) as Promise<StaffCourse>,
    onSuccess: async (course) => {
      await qc.invalidateQueries({ queryKey: ["cur-courses"] });
      setCourseId(course.id);
      setTab("content");
    },
    onError: failure,
  });
  const selected = courseId ?? courses.data?.find((c) => c.can_manage)?.id ?? courses.data?.[0]?.id ?? null;
  return (
    <div className="cur-page cur-studio">
      <div className="workspace-edition">
        <span>DOCENCIA &nbsp;/&nbsp; CURRÍCULO</span>
        <span>CURSO · MÓDULO · LECCIÓN · ACTIVIDAD</span>
      </div>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">DISEÑO DEL CURSO</p>
        <h1>Currículo</h1>
        <p>Organiza el año en módulos, escribe lecciones propias en español y conecta cada actividad con su evaluación.</p>
      </header>
      <div className="cur-studio-grid">
        <aside className="cur-course-list" aria-label="Cursos">
          <div className="cur-list-head">
            <span>CURSOS</span>
            <Button variant="outline" onClick={() => create.mutate()} disabled={create.isPending}>
              <Plus size={14} /> Nuevo
            </Button>
          </div>
          {courses.isLoading ? (
            <p className="cur-note">Cargando…</p>
          ) : courses.isError ? (
            <ErrorState onRetry={() => courses.refetch()} />
          ) : !courses.data?.length ? (
            <p className="cur-note">Crea tu primer curso.</p>
          ) : (
            courses.data.map((course) => (
              <button key={course.id} className={`cur-course-item ${course.id === selected ? "selected" : ""}`} onClick={() => setCourseId(course.id)}>
                <strong>{course.title}</strong>
                <small>
                  {course.is_template ? "Plantilla compartida" : publishLabel[course.status]} · {course.module_count} módulos
                </small>
              </button>
            ))
          )}
        </aside>
        <section className="cur-workspace">
          {selected === null ? (
            <EmptyState title="Sin cursos todavía" description="Crea un curso o duplica la plantilla del plan anual." />
          ) : (
            <>
              <div className="edu-filters cur-tabs" role="tablist" aria-label="Vista del curso">
                {(
                  [
                    ["content", "Contenido"],
                    ["progress", "Progreso"],
                    ["reviews", "Revisión"],
                  ] as const
                ).map(([key, label]) => (
                  <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "selected" : ""} onClick={() => setTab(key)}>
                    {label}
                  </button>
                ))}
              </div>
              {tab === "content" && <CourseContent key={selected} courseId={selected} onDuplicated={setCourseId} />}
              {tab === "progress" && <ProgressMatrix courseId={selected} />}
              {tab === "reviews" && <ReviewQueue />}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function CourseContent({ courseId, onDuplicated }: { courseId: number; onDuplicated: (id: number) => void }) {
  const qc = useQueryClient();
  const [selection, setSelection] = useState<Selection>({ kind: "course" });
  const q = useQuery({
    queryKey: ["cur-course", courseId],
    queryFn: async () => (await unwrap(await api.GET("/api/v1/curriculum/courses/{course_id}", { params: { path: { course_id: courseId } } }))) as StaffCourse,
  });
  const duplicate = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/curriculum/courses/{course_id}/duplicate", { params: { path: { course_id: courseId } } })) as Promise<StaffCourse>,
    onSuccess: async (copy) => {
      toast("Copia creada como borrador. Ya puedes editarla y asignarla a tu clase.");
      await qc.invalidateQueries({ queryKey: ["cur-courses"] });
      onDuplicated(copy.id);
    },
    onError: failure,
  });
  if (q.isLoading) return <div className="edu-empty">Cargando curso…</div>;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const course = q.data;
  const editable = course.can_manage;
  return (
    <div className="cur-content-grid">
      <nav className="cur-tree" aria-label="Estructura del curso">
        <button className={`cur-tree-course ${selection.kind === "course" ? "selected" : ""}`} onClick={() => setSelection({ kind: "course" })}>
          <BookOpen size={15} /> {course.title}
        </button>
        {!editable && (
          <div className="cur-template-note">
            <Lock size={13} />
            <span>Plantilla compartida: solo la administración la edita.</span>
            <Button variant="outline" onClick={() => duplicate.mutate()} disabled={duplicate.isPending}>
              <BookCopy size={14} /> Duplicar para mi clase
            </Button>
          </div>
        )}
        {(course.modules ?? []).map((module, mi) => (
          <div className="cur-tree-module" key={module.id}>
            <button className={selection.kind === "module" && selection.module?.id === module.id ? "selected" : ""} onClick={() => setSelection({ kind: "module", module })}>
              <span className="cur-index-number">{String(mi + 1).padStart(2, "0")}</span>
              <Layers size={14} /> {module.title}
              {module.status !== "PUBLISHED" && <em>borrador</em>}
            </button>
            {module.lessons.map((lesson) => (
              <div className="cur-tree-lesson" key={lesson.id}>
                <button className={selection.kind === "lesson" && selection.lesson?.id === lesson.id ? "selected" : ""} onClick={() => setSelection({ kind: "lesson", moduleId: module.id, lesson })}>
                  <FilePen size={13} /> {lesson.title}
                  {lesson.status !== "PUBLISHED" && <em>borrador</em>}
                </button>
                {lesson.activities.map((activity) => (
                  <button
                    key={activity.id}
                    className={`cur-tree-activity ${selection.kind === "activity" && selection.activity?.id === activity.id ? "selected" : ""}`}
                    onClick={() => setSelection({ kind: "activity", lessonId: lesson.id, activity })}
                  >
                    <small>{kindLabel[activity.type]}</small> {activity.title}
                    {activity.status !== "PUBLISHED" && <em>borrador</em>}
                  </button>
                ))}
                {editable && (
                  <button className="cur-tree-add" onClick={() => setSelection({ kind: "activity", lessonId: lesson.id, activity: null })}>
                    <Plus size={12} /> Actividad
                  </button>
                )}
              </div>
            ))}
            {editable && (
              <button className="cur-tree-add" onClick={() => setSelection({ kind: "lesson", moduleId: module.id, lesson: null })}>
                <Plus size={12} /> Lección
              </button>
            )}
          </div>
        ))}
        {editable && (
          <button className="cur-tree-add" onClick={() => setSelection({ kind: "module", module: null })}>
            <Plus size={12} /> Módulo
          </button>
        )}
      </nav>
      <div className="cur-panel">
        {selection.kind === "course" && <CourseEditor key={`c-${course.id}`} course={course} />}
        {selection.kind === "module" && editable && <ModuleEditor key={`m-${selection.module?.id ?? "new"}`} course={course} module={selection.module} />}
        {selection.kind === "lesson" && editable && <LessonEditor key={`l-${selection.lesson?.id ?? "new"}-${selection.moduleId}`} course={course} moduleId={selection.moduleId} lesson={selection.lesson} />}
        {selection.kind === "activity" && editable && (
          <ActivityEditor key={`a-${selection.activity?.id ?? "new"}-${selection.lessonId}`} course={course} lessonId={selection.lessonId} activity={selection.activity} onDone={() => setSelection({ kind: "course" })} />
        )}
        {selection.kind !== "course" && !editable && <ReadOnlyItem selection={selection} />}
      </div>
    </div>
  );
}

function ReadOnlyItem({ selection }: { selection: Selection }) {
  const item = selection.kind === "module" ? selection.module : selection.kind === "lesson" ? selection.lesson : selection.kind === "activity" ? selection.activity : null;
  if (!item) return null;
  const body = "content_markdown" in item ? item.content_markdown : item.description_markdown;
  return (
    <div className="cur-editor">
      <p className="page-eyebrow">VISTA DE LA PLANTILLA</p>
      <h2>{item.title}</h2>
      <Markdown source={body} />
    </div>
  );
}

function useInvalidate(courseId: number) {
  const qc = useQueryClient();
  return async () => {
    await qc.invalidateQueries({ queryKey: ["cur-course", courseId] });
    await qc.invalidateQueries({ queryKey: ["cur-courses"] });
  };
}

function CourseEditor({ course }: { course: StaffCourse }) {
  const refresh = useInvalidate(course.id);
  const [title, setTitle] = useState(course.title);
  const [description, setDescription] = useState(course.description_markdown);
  const [status, setStatus] = useState<Status>(course.status === "ARCHIVED" ? "DRAFT" : course.status);
  const [classIds, setClassIds] = useState<number[]>(course.class_ids);
  const classes = useQuery({
    queryKey: ["cur-classes"],
    queryFn: async () => ((await unwrap(await api.GET("/api/v1/classes", { params: { query: { page: 1, page_size: 100 } } }))) as { items: { id: number; name: string; academic_period: string }[] }).items,
  });
  const save = useMutation({
    mutationFn: async () => {
      await unwrap(await api.PUT("/api/v1/curriculum/courses/{course_id}", { params: { path: { course_id: course.id } }, body: { title, description_markdown: description, status } }));
      return unwrap(await api.PUT("/api/v1/curriculum/courses/{course_id}/classes", { params: { path: { course_id: course.id } }, body: { class_ids: classIds } }));
    },
    onSuccess: async () => {
      toast("Curso guardado.");
      await refresh();
    },
    onError: failure,
  });
  const remove = useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/v1/curriculum/courses/{course_id}", { params: { path: { course_id: course.id } } })),
    onSuccess: async () => {
      toast("Curso archivado.");
      await refresh();
    },
    onError: failure,
  });
  if (!course.can_manage)
    return (
      <div className="cur-editor">
        <p className="page-eyebrow">PLANTILLA COMPARTIDA</p>
        <h2>{course.title}</h2>
        <Markdown source={course.description_markdown} />
        <p className="cur-note">Selecciona un módulo o una lección para leer su contenido.</p>
      </div>
    );
  return (
    <form
      className="cur-editor"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <p className="page-eyebrow">CURSO</p>
      <label>
        Título del curso
        <Input value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} />
      </label>
      <label>
        Estado
        <Select value={status} onValueChange={(v) => setStatus(v as Status)} options={statusOptions} />
      </label>
      <MarkdownField label="Presentación (Markdown)" value={description} onChange={setDescription} rows={4} />
      <fieldset className="cur-fieldset">
        <legend>Clases que reciben el curso</legend>
        {(classes.data ?? []).length === 0 && <small>No tienes clases asignadas.</small>}
        {(classes.data ?? []).map((c) => (
          <Checkbox key={c.id} label={c.academic_period ? `${c.name} · ${c.academic_period}` : c.name} checked={classIds.includes(c.id)} onCheckedChange={(v) => setClassIds(v ? [...classIds, c.id] : classIds.filter((x) => x !== c.id))} />
        ))}
        <small>Los estudiantes solo ven lo publicado: curso, módulo, lección y actividad deben estar en «Publicado».</small>
      </fieldset>
      <div className="cur-actions">
        <Button type="submit" disabled={save.isPending || title.trim().length < 2}>
          <Save size={14} /> Guardar curso
        </Button>
        <Button
          type="button"
          variant="quiet"
          onClick={() => {
            if (window.confirm("¿Archivar este curso? Dejará de verse para los estudiantes.")) remove.mutate();
          }}
        >
          <Trash2 size={14} /> Archivar
        </Button>
      </div>
    </form>
  );
}

function MarkdownField({ label, value, onChange, rows }: { label: string; value: string; onChange: (v: string) => void; rows: number }) {
  const [preview, setPreview] = useState(false);
  return (
    <div className="cur-markdown-field">
      <div className="cur-markdown-head">
        <span>{label}</span>
        <Button type="button" variant="quiet" onClick={() => setPreview(!preview)}>
          {preview ? <FilePen size={13} /> : <Eye size={13} />} {preview ? "Editar" : "Vista previa"}
        </Button>
      </div>
      {preview ? <div className="cur-preview">{value.trim() ? <Markdown source={value} /> : <small>Sin contenido todavía.</small>}</div> : <Textarea aria-label={label} rows={rows} value={value} onChange={(e) => onChange(e.target.value)} />}
    </div>
  );
}

function ModuleEditor({ course, module }: { course: StaffCourse; module: StaffModule | null }) {
  const refresh = useInvalidate(course.id);
  const [title, setTitle] = useState(module?.title ?? "");
  const [description, setDescription] = useState(module?.description_markdown ?? "");
  const [order, setOrder] = useState(module?.sort_order ?? (course.modules?.length ?? 0) + 1);
  const [status, setStatus] = useState<Status>(module?.status === "PUBLISHED" ? "PUBLISHED" : "DRAFT");
  const save = useMutation({
    mutationFn: async () => {
      const body = { title, description_markdown: description, sort_order: order, status };
      return module
        ? unwrap(await api.PUT("/api/v1/curriculum/modules/{module_id}", { params: { path: { module_id: module.id } }, body }))
        : unwrap(await api.POST("/api/v1/curriculum/courses/{course_id}/modules", { params: { path: { course_id: course.id } }, body }));
    },
    onSuccess: async () => {
      toast(module ? "Módulo actualizado." : "Módulo creado.");
      await refresh();
    },
    onError: failure,
  });
  const remove = useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/v1/curriculum/modules/{module_id}", { params: { path: { module_id: module!.id } } })),
    onSuccess: refresh,
    onError: failure,
  });
  return (
    <form
      className="cur-editor"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <p className="page-eyebrow">{module ? "MÓDULO" : "NUEVO MÓDULO"}</p>
      <label>
        Título del módulo
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="p. ej. Mes 1 · Linux y fundamentos" required minLength={2} />
      </label>
      <div className="cur-grid-2">
        <label>
          Orden
          <Input type="number" min={0} value={order} onChange={(e) => setOrder(Number(e.target.value))} />
        </label>
        <label>
          Estado
          <Select value={status} onValueChange={(v) => setStatus(v as Status)} options={statusOptions} />
        </label>
      </div>
      <MarkdownField label="Objetivo del módulo" value={description} onChange={setDescription} rows={3} />
      <div className="cur-actions">
        <Button type="submit" disabled={save.isPending || title.trim().length < 2}>
          <Save size={14} /> {module ? "Guardar módulo" : "Crear módulo"}
        </Button>
        {module && (
          <Button type="button" variant="quiet" onClick={() => window.confirm("¿Archivar el módulo y su contenido?") && remove.mutate()}>
            <Trash2 size={14} /> Archivar
          </Button>
        )}
      </div>
    </form>
  );
}

function LessonEditor({ course, moduleId, lesson }: { course: StaffCourse; moduleId: number; lesson: StaffLesson | null }) {
  const refresh = useInvalidate(course.id);
  const [title, setTitle] = useState(lesson?.title ?? "");
  const [content, setContent] = useState(lesson?.content_markdown ?? "");
  const [minutes, setMinutes] = useState<number | null>(lesson?.estimated_minutes ?? null);
  const [order, setOrder] = useState(lesson?.sort_order ?? 0);
  const [status, setStatus] = useState<Status>(lesson?.status === "PUBLISHED" ? "PUBLISHED" : "DRAFT");
  const save = useMutation({
    mutationFn: async () => {
      const body = { title, content_markdown: content, estimated_minutes: minutes, sort_order: order, status };
      return lesson
        ? unwrap(await api.PUT("/api/v1/curriculum/lessons/{lesson_id}", { params: { path: { lesson_id: lesson.id } }, body }))
        : unwrap(await api.POST("/api/v1/curriculum/modules/{module_id}/lessons", { params: { path: { module_id: moduleId } }, body }));
    },
    onSuccess: async () => {
      toast(lesson ? "Lección actualizada." : "Lección creada.");
      await refresh();
    },
    onError: failure,
  });
  const remove = useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/v1/curriculum/lessons/{lesson_id}", { params: { path: { lesson_id: lesson!.id } } })),
    onSuccess: refresh,
    onError: failure,
  });
  return (
    <form
      className="cur-editor"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <p className="page-eyebrow">{lesson ? "LECCIÓN" : "NUEVA LECCIÓN"}</p>
      <label>
        Título de la lección
        <Input value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} />
      </label>
      <div className="cur-grid-3">
        <label>
          Minutos estimados
          <Input type="number" min={1} value={minutes ?? ""} onChange={(e) => setMinutes(e.target.value ? Number(e.target.value) : null)} />
        </label>
        <label>
          Orden
          <Input type="number" min={0} value={order} onChange={(e) => setOrder(Number(e.target.value))} />
        </label>
        <label>
          Estado
          <Select value={status} onValueChange={(v) => setStatus(v as Status)} options={statusOptions} />
        </label>
      </div>
      <MarkdownField label="Contenido de la lección (Markdown)" value={content} onChange={setContent} rows={12} />
      <div className="cur-actions">
        <Button type="submit" disabled={save.isPending || title.trim().length < 2}>
          <Save size={14} /> {lesson ? "Guardar lección" : "Crear lección"}
        </Button>
        {lesson && (
          <Button type="button" variant="quiet" onClick={() => window.confirm("¿Archivar la lección y sus actividades?") && remove.mutate()}>
            <Trash2 size={14} /> Archivar
          </Button>
        )}
      </div>
    </form>
  );
}

function ProgressMatrix({ courseId }: { courseId: number }) {
  const q = useQuery({
    queryKey: ["cur-progress", courseId],
    queryFn: async () => (await unwrap(await api.GET("/api/v1/curriculum/courses/{course_id}/progress", { params: { path: { course_id: courseId } } }))) as CourseProgress,
  });
  if (q.isLoading) return <div className="edu-empty">Calculando avance…</div>;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data.students.length) return <EmptyState title="Sin estudiantes todavía" description="Asigna el curso a una clase en la pestaña Contenido." />;
  return (
    <div className="edu-table-scroll">
      <table className="edu-table cur-matrix">
        <thead>
          <tr>
            <th>ESTUDIANTE</th>
            {q.data.modules.map((m, i) => (
              <th key={m.public_id} title={m.title}>
                {String(i + 1).padStart(2, "0")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {q.data.students.map((s) => (
            <tr key={s.student_id}>
              <td>
                <strong>{s.display_name}</strong>
                {s.pending_review && <small className="edu-hint">Entrega pendiente de revisión</small>}
              </td>
              {s.modules.map((cell) => {
                const pct = cell.total ? Math.round((cell.completed / cell.total) * 100) : 0;
                return (
                  <td key={cell.module_public_id} className="cur-cell" title={`${cell.completed}/${cell.total}`}>
                    <span style={{ width: `${pct}%` }} />
                    {cell.total ? `${pct}%` : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReviewQueue() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cur-reviews"], queryFn: async () => (await unwrap(await api.GET("/api/v1/curriculum/reviews", { params: { query: { status: "PENDING_REVIEW" } } }))) as ReviewRow[] });
  const decide = useMutation({
    mutationFn: async (input: { id: number; decision: "APPROVED" | "REJECTED" | "NEEDS_CHANGES"; score: number | null; feedback: string }) =>
      unwrap(await api.POST("/api/v1/curriculum/reviews/{progress_id}/decision", { params: { path: { progress_id: input.id } }, body: { decision: input.decision, score: input.score, feedback: input.feedback } })),
    onSuccess: async () => {
      toast("Revisión registrada y notificada al estudiante.");
      await qc.invalidateQueries({ queryKey: ["cur-reviews"] });
      await qc.invalidateQueries({ queryKey: ["cur-progress"] });
    },
    onError: failure,
  });
  if (q.isLoading) return <div className="edu-empty">Cargando entregas…</div>;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  if (!q.data?.length) return <EmptyState title="Nada pendiente" description="Las entregas de proyectos y ejercicios abiertos aparecerán aquí." />;
  return (
    <div className="cur-reviews">
      {q.data.map((row) => (
        <ReviewCard key={row.id} row={row} pending={decide.isPending} onDecide={(decision, score, feedback) => decide.mutate({ id: row.id, decision, score, feedback })} />
      ))}
    </div>
  );
}

function ReviewCard({ row, pending, onDecide }: { row: ReviewRow; pending: boolean; onDecide: (d: "APPROVED" | "REJECTED" | "NEEDS_CHANGES", score: number | null, feedback: string) => void }) {
  const [score, setScore] = useState(row.points);
  const [feedback, setFeedback] = useState("");
  return (
    <article className="cur-review">
      <header>
        <div>
          <small className="cur-kind">
            {kindLabel[row.activity_type]} · {row.course} · intento {row.attempts}
          </small>
          <h3>{row.activity}</h3>
          <span>{row.student}</span>
        </div>
        <Badge status="live">En revisión</Badge>
      </header>
      {row.submission.answer && <blockquote>{row.submission.answer}</blockquote>}
      {row.submission.text && <blockquote>{row.submission.text}</blockquote>}
      {row.submission.url && (
        <p>
          Enlace:{" "}
          <a href={row.submission.url} target="_blank" rel="noopener noreferrer nofollow">
            {row.submission.url}
          </a>
        </p>
      )}
      <div className="cur-grid-2">
        <label>
          Puntuación (0–{row.points})
          <Input type="number" min={0} max={row.points} value={score} onChange={(e) => setScore(Number(e.target.value))} />
        </label>
        <label>
          Comentario para el estudiante
          <Textarea rows={2} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
        </label>
      </div>
      <div className="cur-actions">
        <Button disabled={pending} onClick={() => onDecide("APPROVED", score, feedback)}>
          <CheckCircle2 size={14} /> Aprobar
        </Button>
        <Button variant="outline" disabled={pending || !feedback.trim()} onClick={() => onDecide("NEEDS_CHANGES", null, feedback)}>
          Pedir cambios
        </Button>
        <Button variant="quiet" disabled={pending || !feedback.trim()} onClick={() => onDecide("REJECTED", null, feedback)}>
          Rechazar
        </Button>
      </div>
    </article>
  );
}
