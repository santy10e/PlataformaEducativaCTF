import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Trash2 } from "lucide-react";
import { api, ApiError, unwrap } from "../../api/client";
import { Button, Checkbox, Input, Select, Textarea, toast } from "../../components/ui";
import { kindLabel, publishLabel, type ActivityKind, type QuizQuestion, type StaffActivity, type StaffCourse, type Status } from "./types";

type Option = { id: number; name: string };
type Draft = Omit<StaffActivity, "id" | "public_id" | "lesson_id" | "hints">;

const blank = (type: ActivityKind): Draft => ({
  type,
  title: "",
  description_markdown: "",
  sort_order: 0,
  category_id: null,
  difficulty_id: null,
  points: 100,
  xp: 0,
  status: "DRAFT",
  prerequisite_ids: [],
  config: type === "quiz" ? { questions: [newQuestion()], max_attempts: null } : type === "exercise" ? { accepted_answers: [], case_sensitive: false, max_attempts: null } : type === "project" ? { accept: ["text", "url"] } : {},
});

function newQuestion(): QuizQuestion {
  return { id: Math.random().toString(36).slice(2, 10), prompt: "", kind: "single", options: ["", ""], correct: [0], points: 1 };
}

function failure(error: unknown) {
  toast(error instanceof ApiError ? error.message : "No se pudo guardar.");
}

export function ActivityEditor({ course, lessonId, activity, onDone }: { course: StaffCourse; lessonId: number; activity: StaffActivity | null; onDone: () => void }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => (activity ? { ...activity } : blank("lesson_read")));
  const categories = useQuery({ queryKey: ["ctf-categories"], queryFn: async () => (await unwrap(await api.GET("/api/v1/ctf/categories"))) as Option[] });
  const difficulties = useQuery({ queryKey: ["ctf-difficulties"], queryFn: async () => (await unwrap(await api.GET("/api/v1/ctf/difficulties"))) as Option[] });
  const others = useMemo(
    () => (course.modules ?? []).flatMap((m) => m.lessons.flatMap((l) => l.activities.map((a) => ({ ...a, where: `${m.title} › ${l.title}` })))).filter((a) => a.id !== activity?.id),
    [course, activity],
  );
  const save = useMutation({
    mutationFn: async () => {
      const body = { ...draft, title: draft.title.trim() };
      return activity
        ? unwrap(await api.PUT("/api/v1/curriculum/activities/{activity_id}", { params: { path: { activity_id: activity.id } }, body }))
        : unwrap(await api.POST("/api/v1/curriculum/lessons/{lesson_id}/activities", { params: { path: { lesson_id: lessonId } }, body }));
    },
    onSuccess: async () => {
      toast(activity ? "Actividad actualizada." : "Actividad creada.");
      await qc.invalidateQueries({ queryKey: ["cur-course", course.id] });
      if (!activity) onDone();
    },
    onError: failure,
  });
  const set = (patch: Partial<Draft>) => setDraft((current) => ({ ...current, ...patch }));
  const setConfig = (patch: Record<string, unknown>) => setDraft((current) => ({ ...current, config: { ...current.config, ...patch } }));
  return (
    <form
      className="cur-editor"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <p className="page-eyebrow">{activity ? `ACTIVIDAD · ${kindLabel[activity.type].toUpperCase()}` : "NUEVA ACTIVIDAD"}</p>
      {!activity && (
        <label>
          Tipo de actividad
          <Select value={draft.type} onValueChange={(v) => setDraft(blank(v as ActivityKind))} options={(Object.keys(kindLabel) as ActivityKind[]).map((k) => ({ value: k, label: kindLabel[k] }))} />
        </label>
      )}
      <label>
        Título
        <Input value={draft.title} onChange={(e) => set({ title: e.target.value })} required minLength={2} />
      </label>
      <div className="cur-grid-3">
        <label>
          Puntos
          <Input type="number" min={0} value={draft.points} onChange={(e) => set({ points: Number(e.target.value) })} />
        </label>
        <label>
          XP
          <Input type="number" min={0} value={draft.xp} onChange={(e) => set({ xp: Number(e.target.value) })} />
        </label>
        <label>
          Orden
          <Input type="number" min={0} value={draft.sort_order} onChange={(e) => set({ sort_order: Number(e.target.value) })} />
        </label>
      </div>
      <div className="cur-grid-3">
        <label>
          Categoría
          <Select value={draft.category_id ? String(draft.category_id) : "none"} onValueChange={(v) => set({ category_id: v === "none" ? null : Number(v) })} options={[{ value: "none", label: "Sin categoría" }, ...(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))]} />
        </label>
        <label>
          Dificultad
          <Select value={draft.difficulty_id ? String(draft.difficulty_id) : "none"} onValueChange={(v) => set({ difficulty_id: v === "none" ? null : Number(v) })} options={[{ value: "none", label: "Sin dificultad" }, ...(difficulties.data ?? []).map((d) => ({ value: String(d.id), label: d.name }))]} />
        </label>
        <label>
          Estado
          <Select value={draft.status} onValueChange={(v) => set({ status: v as Status })} options={(["DRAFT", "PUBLISHED"] as Status[]).map((s) => ({ value: s, label: publishLabel[s] }))} />
        </label>
      </div>
      <label>
        Enunciado (Markdown)
        <Textarea rows={4} value={draft.description_markdown} onChange={(e) => set({ description_markdown: e.target.value })} />
      </label>
      {draft.type === "quiz" && <QuizBuilder config={draft.config} onChange={setConfig} />}
      {draft.type === "exercise" && (
        <fieldset className="cur-fieldset">
          <legend>Corrección</legend>
          <label>
            Respuestas aceptadas (una por línea; vacío = revisión del docente)
            <Textarea rows={3} value={((draft.config.accepted_answers as string[]) ?? []).join("\n")} onChange={(e) => setConfig({ accepted_answers: e.target.value.split("\n").map((x) => x.trim()).filter(Boolean) })} />
          </label>
          <Checkbox label="Distinguir mayúsculas y minúsculas" checked={draft.config.case_sensitive === true} onCheckedChange={(v) => setConfig({ case_sensitive: v })} />
          <MaxAttempts value={draft.config.max_attempts as number | null} onChange={(v) => setConfig({ max_attempts: v })} />
        </fieldset>
      )}
      {draft.type === "project" && (
        <fieldset className="cur-fieldset">
          <legend>Formato de la entrega</legend>
          {(["text", "url"] as const).map((kind) => {
            const accept = (draft.config.accept as string[]) ?? [];
            return (
              <Checkbox key={kind} label={kind === "text" ? "Texto" : "Enlace"} checked={accept.includes(kind)} onCheckedChange={(v) => setConfig({ accept: v ? [...accept, kind] : accept.filter((x) => x !== kind) })} />
            );
          })}
        </fieldset>
      )}
      {draft.type === "ctf_challenge" && <CtfPicker value={draft.config.challenge_id as number | undefined} onChange={(id) => setConfig({ challenge_id: id })} />}
      {others.length > 0 && (
        <fieldset className="cur-fieldset">
          <legend>Prerrequisitos (deben completarse antes)</legend>
          <div className="cur-prereqs">
            {others.map((a) => (
              <Checkbox
                key={a.id}
                label={`${a.title} — ${a.where}`}
                checked={draft.prerequisite_ids.includes(a.id)}
                onCheckedChange={(v) => set({ prerequisite_ids: v ? [...draft.prerequisite_ids, a.id] : draft.prerequisite_ids.filter((x) => x !== a.id) })}
              />
            ))}
          </div>
        </fieldset>
      )}
      <div className="cur-actions">
        <Button type="submit" disabled={save.isPending || draft.title.trim().length < 2}>
          <Save size={14} /> {activity ? "Guardar cambios" : "Crear actividad"}
        </Button>
      </div>
      {activity && <HintManager course={course} activity={activity} />}
    </form>
  );
}

function MaxAttempts({ value, onChange }: { value: number | null; onChange: (v: number | null) => void }) {
  return (
    <label>
      Intentos máximos (vacío = sin límite)
      <Input type="number" min={1} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)} />
    </label>
  );
}

function QuizBuilder({ config, onChange }: { config: Record<string, unknown>; onChange: (patch: Record<string, unknown>) => void }) {
  const questions = (config.questions as QuizQuestion[]) ?? [];
  const update = (index: number, patch: Partial<QuizQuestion>) => onChange({ questions: questions.map((q, i) => (i === index ? { ...q, ...patch } : q)) });
  return (
    <fieldset className="cur-fieldset">
      <legend>Preguntas ({questions.length})</legend>
      {questions.map((q, qi) => (
        <div className="cur-question" key={q.id}>
          <div className="cur-question-head">
            <strong>{String(qi + 1).padStart(2, "0")}</strong>
            <Select
              value={q.kind}
              onValueChange={(v) => update(qi, v === "text" ? { kind: "text", accepted: q.accepted ?? [""], options: undefined, correct: undefined } : { kind: v as "single" | "multiple", options: q.options ?? ["", ""], correct: [0], accepted: undefined })}
              options={[{ value: "single", label: "Una respuesta" }, { value: "multiple", label: "Varias respuestas" }, { value: "text", label: "Respuesta escrita" }]}
            />
            <Input aria-label={`Puntos de la pregunta ${qi + 1}`} type="number" min={1} max={100} value={q.points} onChange={(e) => update(qi, { points: Number(e.target.value) })} />
            <Button type="button" variant="quiet" aria-label={`Quitar la pregunta ${qi + 1}`} onClick={() => onChange({ questions: questions.filter((_, i) => i !== qi) })} disabled={questions.length === 1}>
              <Trash2 size={14} />
            </Button>
          </div>
          <Textarea aria-label={`Enunciado de la pregunta ${qi + 1}`} rows={2} value={q.prompt} placeholder="Enunciado de la pregunta" onChange={(e) => update(qi, { prompt: e.target.value })} />
          {q.kind === "text" ? (
            <Input aria-label={`Respuestas aceptadas de la pregunta ${qi + 1}`} placeholder="Respuestas aceptadas separadas por ;" value={(q.accepted ?? []).join("; ")} onChange={(e) => update(qi, { accepted: e.target.value.split(";").map((x) => x.trim()) })} />
          ) : (
            <>
              {(q.options ?? []).map((option, oi) => (
                <div className="cur-option-edit" key={oi}>
                  <Checkbox
                    label="Correcta"
                    checked={(q.correct ?? []).includes(oi)}
                    onCheckedChange={(v) => update(qi, { correct: q.kind === "single" ? [oi] : v ? [...(q.correct ?? []), oi] : (q.correct ?? []).filter((x) => x !== oi) })}
                  />
                  <Input aria-label={`Opción ${oi + 1} de la pregunta ${qi + 1}`} value={option} onChange={(e) => update(qi, { options: (q.options ?? []).map((o, i) => (i === oi ? e.target.value : o)) })} />
                </div>
              ))}
              <Button type="button" variant="quiet" onClick={() => update(qi, { options: [...(q.options ?? []), ""] })} disabled={(q.options ?? []).length >= 10}>
                <Plus size={13} /> Opción
              </Button>
            </>
          )}
        </div>
      ))}
      <Button type="button" variant="outline" onClick={() => onChange({ questions: [...questions, newQuestion()] })}>
        <Plus size={14} /> Añadir pregunta
      </Button>
      <MaxAttempts value={(config.max_attempts as number | null) ?? null} onChange={(v) => onChange({ max_attempts: v })} />
    </fieldset>
  );
}

type EventRow = { id: number; name: string };
type ChallengeRow = { id: number; title: string; status: string };

function CtfPicker({ value, onChange }: { value: number | undefined; onChange: (id: number) => void }) {
  const [eventId, setEventId] = useState<string>("");
  const events = useQuery({
    queryKey: ["cur-ctf-events"],
    queryFn: async () => ((await unwrap(await api.GET("/api/v1/ctf/events", { params: { query: { page: 1, page_size: 100 } } }))) as { items: EventRow[] }).items,
  });
  const challenges = useQuery({
    queryKey: ["cur-ctf-challenges", eventId],
    enabled: eventId !== "",
    queryFn: async () => (await unwrap(await api.GET("/api/v1/ctf/events/{event_id}/challenges", { params: { path: { event_id: Number(eventId) } } }))) as ChallengeRow[],
  });
  return (
    <fieldset className="cur-fieldset">
      <legend>Reto CTF enlazado</legend>
      {value && <small>Reto seleccionado: #{value}</small>}
      <div className="cur-grid-2">
        <label>
          Evento
          <Select value={eventId || undefined} placeholder="Elige un evento" onValueChange={setEventId} options={(events.data ?? []).map((e) => ({ value: String(e.id), label: e.name }))} />
        </label>
        <label>
          Reto
          <Select
            value={value ? String(value) : undefined}
            placeholder="Elige un reto"
            disabled={!eventId}
            onValueChange={(v) => onChange(Number(v))}
            options={(challenges.data ?? []).map((c) => ({ value: String(c.id), label: `${c.title}${c.status === "PUBLISHED" ? "" : " (borrador)"}` }))}
          />
        </label>
      </div>
      <small>El progreso y la puntuación del reto vienen del motor CTF: el estudiante lo resuelve en la pantalla del reto.</small>
    </fieldset>
  );
}

function HintManager({ course, activity }: { course: StaffCourse; activity: StaffActivity }) {
  const qc = useQueryClient();
  const [content, setContent] = useState("");
  const [cost, setCost] = useState(5);
  const refresh = () => qc.invalidateQueries({ queryKey: ["cur-course", course.id] });
  const add = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/curriculum/activities/{activity_id}/hints", { params: { path: { activity_id: activity.id } }, body: { order: (activity.hints.at(-1)?.order ?? 0) + 1, cost, content_markdown: content } })),
    onSuccess: async () => {
      setContent("");
      await refresh();
    },
    onError: failure,
  });
  const remove = useMutation({
    mutationFn: async (hintId: number) => unwrap(await api.DELETE("/api/v1/curriculum/activities/{activity_id}/hints/{hint_id}", { params: { path: { activity_id: activity.id, hint_id: hintId } } })),
    onSuccess: refresh,
    onError: failure,
  });
  if (activity.type === "ctf_challenge") return <p className="cur-note">Las pistas de un reto CTF se gestionan en el propio reto, desde «Diseñar CTF».</p>;
  return (
    <fieldset className="cur-fieldset">
      <legend>Pistas en orden ({activity.hints.length})</legend>
      {activity.hints.map((hint) => (
        <div className="cur-hint-row" key={hint.id}>
          <strong>{hint.order}</strong>
          <span>{hint.content_markdown}</span>
          <small>−{hint.cost} pts</small>
          <Button type="button" variant="quiet" aria-label={`Borrar la pista ${hint.order}`} onClick={() => remove.mutate(hint.id)}>
            <Trash2 size={13} />
          </Button>
        </div>
      ))}
      <div className="cur-hint-new">
        <Textarea aria-label="Nueva pista" rows={2} placeholder="Una pista que oriente sin revelar la respuesta" value={content} onChange={(e) => setContent(e.target.value)} />
        <Input aria-label="Costo de la nueva pista" type="number" min={0} max={100} value={cost} onChange={(e) => setCost(Number(e.target.value))} />
        <Button type="button" variant="outline" disabled={!content.trim() || add.isPending} onClick={() => add.mutate()}>
          <Plus size={13} /> Añadir pista
        </Button>
      </div>
    </fieldset>
  );
}
