import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BookOpenCheck, CheckCircle2, Clock3, Lightbulb, Lock, Send, Shield } from "lucide-react";
import { api, ApiError, unwrap } from "../../api/client";
import { Badge, Button, EmptyState, ErrorState, Input, Markdown, Textarea, toast } from "../../components/ui";
import { kindLabel, statusLabel, type CourseOutline, type LearnerActivity, type LearnerLesson, type ProgressStatus } from "./types";
import "./curriculum.css";

function tone(status: ProgressStatus): "done" | "live" | "danger" | "draft" | "blocked" {
  if (status === "APPROVED") return "done";
  if (status === "PENDING_REVIEW" || status === "IN_PROGRESS") return "live";
  if (status === "NEEDS_CHANGES" || status === "REJECTED") return "danger";
  if (status === "UNAVAILABLE") return "blocked";
  return "draft";
}

function failure(error: unknown) {
  toast(error instanceof ApiError ? error.message : "No se pudo completar la acción.");
}

function Meter({ done, total, label }: { done: number; total: number; label: string }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="cur-meter" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <span style={{ width: `${pct}%` }} />
      <small>
        {done}/{total} · {pct}%
      </small>
    </div>
  );
}

export function LearnHomePage() {
  const q = useQuery({ queryKey: ["learn-courses"], queryFn: async () => (await unwrap(await api.GET("/api/v1/learn/courses"))) as CourseOutline[] });
  return (
    <div className="cur-page">
      <div className="workspace-edition">
        <span>CUADERNO PERSONAL &nbsp;/&nbsp; CURRÍCULO</span>
        <span>TU RECORRIDO</span>
      </div>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">APRENDER</p>
        <h1>Tu curso, mes a mes</h1>
        <p>Lecciones en español, actividades y retos ordenados para avanzar sin perderte.</p>
      </header>
      {q.isLoading ? (
        <div className="edu-empty">Cargando tus cursos…</div>
      ) : q.isError ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : !q.data?.length ? (
        <EmptyState title="Aún no tienes cursos asignados" description="Tu docente publicará aquí el currículo de tu clase." />
      ) : (
        q.data.map((course) => {
          const done = course.modules.reduce((n, m) => n + m.completed, 0);
          const total = course.modules.reduce((n, m) => n + m.total, 0);
          return (
            <section className="cur-course" key={course.public_id}>
              <header>
                <div>
                  <h2>{course.title}</h2>
                  <Meter done={done} total={total} label={`Avance en ${course.title}`} />
                </div>
                <Link className="ui-button ui-outline" to={`/learn/courses/${course.public_id}`}>
                  Ver temario <ArrowRight size={14} />
                </Link>
              </header>
              <ol className="cur-index">
                {course.modules.map((module, index) => (
                  <li key={module.public_id}>
                    <span className="cur-index-number">{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <strong>{module.title}</strong>
                      <small>{module.description_markdown}</small>
                    </div>
                    <Meter done={module.completed} total={module.total} label={`Avance en ${module.title}`} />
                  </li>
                ))}
              </ol>
            </section>
          );
        })
      )}
    </div>
  );
}

export function LearnCoursePage() {
  const { publicId = "" } = useParams();
  const q = useQuery({
    queryKey: ["learn-course", publicId],
    queryFn: async () => (await unwrap(await api.GET("/api/v1/learn/courses/{public_id}", { params: { path: { public_id: publicId } } }))) as CourseOutline,
  });
  if (q.isLoading) return <div className="edu-empty">Cargando el temario…</div>;
  if (q.isError || !q.data) return <ErrorState title="Este curso no está disponible" description="Puede que aún no esté publicado para tu clase." />;
  const course = q.data;
  return (
    <div className="cur-page">
      <div className="workspace-edition">
        <Link to="/learn">
          <ArrowLeft size={13} /> CURSOS
        </Link>
        <span>TEMARIO</span>
      </div>
      <header className="workspace-page-heading">
        <p className="page-eyebrow">CURSO</p>
        <h1>{course.title}</h1>
        {course.description_markdown && <Markdown source={course.description_markdown} />}
      </header>
      {course.modules.map((module, index) => (
        <section className="cur-module" key={module.public_id}>
          <header>
            <span className="cur-index-number">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <h2>{module.title}</h2>
              <p>{module.description_markdown}</p>
            </div>
            <Meter done={module.completed} total={module.total} label={`Avance en ${module.title}`} />
          </header>
          {module.lessons.map((lesson) => (
            <Link className="cur-lesson-row" key={lesson.public_id} to={`/learn/lessons/${lesson.public_id}`}>
              <BookOpenCheck size={16} />
              <div>
                <strong>{lesson.title}</strong>
                <small>
                  {lesson.activities.length} actividades{lesson.estimated_minutes ? ` · ${lesson.estimated_minutes} min` : ""}
                </small>
              </div>
              <span className="cur-dots" aria-label="Estado de las actividades">
                {lesson.activities.map((a) => (
                  <i key={a.public_id} className={`cur-dot cur-dot-${tone(a.status)}`} title={`${a.title}: ${a.locked ? "Bloqueada" : statusLabel[a.status]}`} />
                ))}
              </span>
              <ArrowRight size={14} />
            </Link>
          ))}
        </section>
      ))}
    </div>
  );
}

export function LearnLessonPage() {
  const { publicId = "" } = useParams();
  const q = useQuery({
    queryKey: ["learn-lesson", publicId],
    queryFn: async () => (await unwrap(await api.GET("/api/v1/learn/lessons/{public_id}", { params: { path: { public_id: publicId } } }))) as LearnerLesson,
  });
  if (q.isLoading) return <div className="edu-empty">Abriendo la lección…</div>;
  if (q.isError || !q.data) return <ErrorState title="Esta lección no está disponible" description="Vuelve al temario y elige otra lección." />;
  const lesson = q.data;
  return (
    <div className="cur-page">
      <div className="workspace-edition">
        <Link to={`/learn/courses/${lesson.course.public_id}`}>
          <ArrowLeft size={13} /> {lesson.course.title.toUpperCase()}
        </Link>
        <span>{lesson.module.title.toUpperCase()}</span>
      </div>
      <article className="cur-lesson">
        <header className="workspace-page-heading">
          <p className="page-eyebrow">LECCIÓN{lesson.estimated_minutes ? ` · ${lesson.estimated_minutes} MIN` : ""}</p>
          <h1>{lesson.title}</h1>
        </header>
        <Markdown source={lesson.content_markdown} />
      </article>
      <section className="cur-activities" aria-label="Actividades de la lección">
        <h2>Actividades</h2>
        {lesson.activities.length ? (
          lesson.activities.map((activity, index) => <ActivityPlayer key={activity.public_id} activity={activity} index={index} lessonId={publicId} />)
        ) : (
          <EmptyState title="Esta lección no tiene actividades" description="Léela con calma; tu docente puede añadir actividades más adelante." />
        )}
      </section>
    </div>
  );
}

function ActivityPlayer({ activity, index, lessonId }: { activity: LearnerActivity; index: number; lessonId: string }) {
  const qc = useQueryClient();
  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["learn-lesson", lessonId] });
    await qc.invalidateQueries({ queryKey: ["learn-courses"] });
  };
  const submit = useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      unwrap(await api.POST("/api/v1/learn/activities/{public_id}/submit", { params: { path: { public_id: activity.public_id } }, body })),
    onSuccess: async (result) => {
      const r = result as { status: ProgressStatus; feedback: string };
      toast(r.status === "PENDING_REVIEW" ? "Entrega enviada a revisión." : r.feedback || statusLabel[r.status]);
      await refresh();
    },
    onError: failure,
  });
  const hint = useMutation({
    mutationFn: async (hintId: number) =>
      unwrap(await api.POST("/api/v1/learn/activities/{public_id}/hints/{hint_id}", { params: { path: { public_id: activity.public_id, hint_id: hintId } } })),
    onSuccess: refresh,
    onError: failure,
  });
  const nextHint = activity.hints.find((h) => !h.unlocked);
  const finished = activity.status === "APPROVED" && activity.type !== "quiz";
  const waiting = activity.status === "PENDING_REVIEW";
  return (
    <article className={`cur-activity ${activity.locked ? "is-locked" : ""}`}>
      <header>
        <span className="cur-index-number">{String(index + 1).padStart(2, "0")}</span>
        <div>
          <small className="cur-kind">
            {kindLabel[activity.type]}
            {activity.difficulty ? ` · ${activity.difficulty}` : ""} · {activity.points} pts
          </small>
          <h3>{activity.title}</h3>
        </div>
        <Badge status={activity.locked ? "blocked" : tone(activity.status)}>{activity.locked ? "Bloqueada" : statusLabel[activity.status]}</Badge>
      </header>
      {activity.locked ? (
        <p className="cur-lock">
          <Lock size={14} /> {activity.lock_reason}
        </p>
      ) : (
        <>
          {activity.description_markdown && <Markdown source={activity.description_markdown} />}
          {activity.score !== null && (
            <p className="cur-score">
              <CheckCircle2 size={14} /> Puntuación: <strong>{activity.score}</strong> / {activity.max_score ?? activity.points}
            </p>
          )}
          {activity.feedback && <p className={`cur-feedback cur-feedback-${tone(activity.status)}`}>{activity.feedback}</p>}
          {activity.type === "lesson_read" && !finished && (
            <Button onClick={() => submit.mutate({})} disabled={submit.isPending}>
              <BookOpenCheck size={14} /> Marcar como leída
            </Button>
          )}
          {activity.type === "quiz" && <QuizForm activity={activity} pending={submit.isPending} onSubmit={(answers) => submit.mutate({ answers })} />}
          {activity.type === "exercise" && !finished && !waiting && <ExerciseForm activity={activity} pending={submit.isPending} onSubmit={(answer) => submit.mutate({ answer })} />}
          {activity.type === "project" && !finished && !waiting && <ProjectForm activity={activity} pending={submit.isPending} onSubmit={(body) => submit.mutate(body)} />}
          {activity.type === "ctf_challenge" &&
            (activity.ctf?.available ? (
              <Link className="ui-button ui-solid" to={`/study/events/${activity.ctf.event_public_id}/challenges/${activity.ctf.challenge_public_id}`}>
                <Shield size={14} /> {activity.status === "APPROVED" ? "Revisar el reto" : "Ir al reto CTF"}
              </Link>
            ) : (
              <p className="cur-lock">
                <Clock3 size={14} /> El reto se abrirá cuando tu docente publique su evento.
              </p>
            ))}
          {waiting && <p className="cur-feedback cur-feedback-live">Tu entrega está en revisión. Te avisaremos cuando tu docente responda.</p>}
          {activity.hints.length > 0 && (
            <div className="cur-hints">
              <h4>
                <Lightbulb size={14} /> Pistas
              </h4>
              {activity.hints
                .filter((h) => h.unlocked)
                .map((h) => (
                  <div className="cur-hint" key={h.id}>
                    <small>
                      Pista {h.order} · −{h.cost} pts
                    </small>
                    <Markdown source={h.content_markdown ?? ""} />
                  </div>
                ))}
              {nextHint && (
                <Button
                  variant="outline"
                  disabled={hint.isPending}
                  onClick={() => {
                    if (window.confirm(`Esta pista cuesta ${nextHint.cost} puntos. ¿Desbloquearla?`)) hint.mutate(nextHint.id);
                  }}
                >
                  Desbloquear pista {nextHint.order} (−{nextHint.cost} pts)
                </Button>
              )}
            </div>
          )}
        </>
      )}
    </article>
  );
}

function QuizForm({ activity, pending, onSubmit }: { activity: LearnerActivity; pending: boolean; onSubmit: (answers: Record<string, number | number[] | string>) => void }) {
  const [answers, setAnswers] = useState<Record<string, number | number[] | string>>({});
  const questions = activity.config.questions ?? [];
  const limit = activity.config.max_attempts;
  const exhausted = limit != null && activity.attempts >= limit;
  return (
    <form
      className="cur-quiz"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(answers);
      }}
    >
      {questions.map((question, qi) => (
        <fieldset key={question.id}>
          <legend>
            {qi + 1}. {question.prompt} <small>({question.points} pt)</small>
          </legend>
          {question.kind === "text" ? (
            <Input aria-label={`Respuesta a la pregunta ${qi + 1}`} value={String(answers[question.id] ?? "")} onChange={(e) => setAnswers({ ...answers, [question.id]: e.target.value })} />
          ) : (
            question.options?.map((option, oi) => {
              const current = answers[question.id];
              const checked = question.kind === "single" ? current === oi : Array.isArray(current) && current.includes(oi);
              return (
                <label className="cur-option" key={oi}>
                  <input
                    type={question.kind === "single" ? "radio" : "checkbox"}
                    name={question.id}
                    checked={checked}
                    onChange={() => {
                      if (question.kind === "single") setAnswers({ ...answers, [question.id]: oi });
                      else {
                        const list = Array.isArray(current) ? current : [];
                        setAnswers({ ...answers, [question.id]: checked ? list.filter((x) => x !== oi) : [...list, oi] });
                      }
                    }}
                  />
                  {option}
                </label>
              );
            })
          )}
        </fieldset>
      ))}
      <div className="cur-actions">
        <Button type="submit" disabled={pending || exhausted}>
          <Send size={14} /> {activity.attempts ? "Enviar de nuevo" : "Enviar respuestas"}
        </Button>
        {limit != null && (
          <small>
            Intentos: {activity.attempts}/{limit}
            {activity.attempts > 0 ? " · se conserva tu mejor resultado" : ""}
          </small>
        )}
      </div>
    </form>
  );
}

function ExerciseForm({ activity, pending, onSubmit }: { activity: LearnerActivity; pending: boolean; onSubmit: (answer: string) => void }) {
  const [answer, setAnswer] = useState("");
  return (
    <form
      className="cur-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(answer);
      }}
    >
      <label>
        Tu respuesta
        <Textarea rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} />
      </label>
      <div className="cur-actions">
        <Button type="submit" disabled={pending || !answer.trim()}>
          <Send size={14} /> Enviar respuesta
        </Button>
        <small>{activity.config.review === "manual" ? "La revisará tu docente." : "Se corrige al instante."}</small>
      </div>
    </form>
  );
}

function ProjectForm({ activity, pending, onSubmit }: { activity: LearnerActivity; pending: boolean; onSubmit: (body: { text?: string; url?: string }) => void }) {
  const accept = activity.config.accept ?? ["text", "url"];
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  return (
    <form
      className="cur-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ ...(text.trim() ? { text } : {}), ...(url.trim() ? { url: url.trim() } : {}) });
      }}
    >
      {accept.includes("text") && (
        <label>
          Entrega escrita
          <Textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} />
        </label>
      )}
      {accept.includes("url") && (
        <label>
          Enlace a tu trabajo
          <Input type="url" placeholder="https://" value={url} onChange={(e) => setUrl(e.target.value)} />
        </label>
      )}
      <div className="cur-actions">
        <Button type="submit" disabled={pending || (!text.trim() && !url.trim())}>
          <Send size={14} /> Entregar proyecto
        </Button>
        <small>Tu docente revisará la entrega y te dejará comentarios.</small>
      </div>
    </form>
  );
}
