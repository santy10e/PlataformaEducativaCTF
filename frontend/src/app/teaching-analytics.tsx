import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Activity, ArrowDownToLine, BellRing, RefreshCw, Users } from "lucide-react";
import { api, unwrap } from "../api/client";
import { Button, Input, Select, toast } from "../components/ui";

type ClassItem = { id: number; name: string; student_count: number };
type StudentRow = { student_id:number; display_name:string; started:number; completed:number; attempts:number; hints:number; score:number; grade:{value:number|string}|null; last_activity:string|null };
type ChallengeSignal = { challenge_id:number; title:string; failures:number; completed:number; started:number; abandoned:number };
type LiveItem = { student_id:number; student:string; challenge_id:number; challenge:string; elapsed_seconds:number; attempts:number; hints:number; score:number; paused:boolean };
type StudentDetail = { student:StudentRow; history:Array<{created_at:string;challenge:string;type:string;points:number}>; categories:Array<{name:string;started:number;completed:number}> };
type Analytics = { scope: { id: number; name: string }; updated_at: string; summary: Record<string, number>; students: StudentRow[]; challenging: ChallengeSignal[]; grade_scales: Array<{id:number;name:string}> };
type Announcement = { id: number; title: string; content_markdown: string; publish_at: string; archived_at?: string | null };
const getJson = async <T,>(path: string): Promise<T> => {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) throw new Error("No se pudieron cargar los datos de la clase.");
  return response.json() as Promise<T>;
};
const postJson = async <T,>(path: string, body?: unknown): Promise<T> => {
  const csrf = document.cookie.split("; ").find((item) => item.startsWith("cyberlab_csrf="))?.split("=").slice(1).join("=");
  const response = await fetch(path, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const result = await response.json();
  if (!response.ok) throw new Error(result?.error?.message ?? "No se pudo guardar el cambio.");
  return result as T;
};

export function TeachingAnalyticsPage() {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [roster, setRoster] = useState<Array<{id:number;display_name:string}>>([]);
  const [classId, setClassId] = useState("");
  const [selectedStudent, setSelectedStudent] = useState("all");
  const [gradeScaleId, setGradeScaleId] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [data, setData] = useState<Analytics | null>(null);
  const [live, setLive] = useState<LiveItem[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [publishAt, setPublishAt] = useState("");
  const [studentDetail, setStudentDetail] = useState<StudentDetail | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { void api.GET("/api/v1/classes", { params: { query: { page: 1, page_size: 100 } } }).then(unwrap).then((r) => { const items = (r as { items: ClassItem[] }).items; setClasses(items); if (items.length) setClassId(String(items[0].id)); }).catch((e: Error) => toast(e.message)); }, []);
  useEffect(() => { if(classId) void getJson<Array<{id:number;display_name:string}>>(`/api/v1/classes/${classId}/students`).then(setRoster).catch((e:Error)=>toast(e.message)); }, [classId]);
  const refresh = useCallback(async (id = classId) => {
    if (!id) return;
    const filters = new URLSearchParams({ class_id: id });
    if (selectedStudent !== "all") filters.set("student_id", selectedStudent);
    if (gradeScaleId !== "all") filters.set("grade_scale_id", gradeScaleId);
    if (dateFrom) filters.set("date_from", `${dateFrom}T00:00:00`);
    if (dateTo) filters.set("date_to", `${dateTo}T23:59:59`);
    const q = filters.toString();
    try {
      const [a, l, n] = await Promise.all([getJson<Analytics>(`/api/v1/teaching/analytics?${q}`), getJson<{ active: LiveItem[] }>(`/api/v1/teaching/live?${q}`), getJson<Announcement[]>(`/api/v1/teaching/announcements?${q}&include_archived=true`)]);
      setData(a); setLive(l.active); setAnnouncements(n);
    } catch (e) { toast(e instanceof Error ? e.message : "No se pudieron actualizar los datos."); }
  }, [classId, selectedStudent, dateFrom, dateTo, gradeScaleId]);
  useEffect(() => { void refresh(classId); const id = window.setInterval(() => { void refresh(classId); }, 30_000); return () => window.clearInterval(id); }, [classId, refresh]);
  async function createAnnouncement(e: FormEvent) {
    e.preventDefault(); if (!title.trim() || !content.trim() || !classId) return;
    setBusy(true);
    try { await postJson("/api/v1/teaching/announcements", { class_id: Number(classId), title, content_markdown: content, publish_at: publishAt ? new Date(publishAt).toISOString() : null }); setTitle(""); setContent(""); setPublishAt(""); await refresh(); toast("Aviso guardado para la clase."); }
    catch (error) { toast(error instanceof Error ? error.message : "No se pudo publicar el aviso."); } finally { setBusy(false); }
  }
  async function archive(id: number) { try { await postJson(`/api/v1/teaching/announcements/${id}/archive`); await refresh(); } catch (e) { toast(e instanceof Error ? e.message : "No se pudo archivar."); } }
  async function showStudent(studentId: number) { try { setStudentDetail(await getJson(`/api/v1/teaching/students/${studentId}?class_id=${classId}`)); } catch (e) { toast(e instanceof Error ? e.message : "No se pudo abrir el historial."); } }
  const metrics = data?.summary;
  return <div className="teaching-analytics">
    <div className="workspace-edition"><span>CUADERNO DOCENTE &nbsp;/&nbsp; SEGUIMIENTO DE APRENDIZAJE</span><span>FASE 08</span></div>
    <header className="workspace-page-heading"><p className="page-eyebrow">AULA · OBSERVACIÓN FORMATIVA</p><h1>El recorrido de tu clase</h1><p>Consulta avances, acompaña el trabajo en curso y comparte indicaciones con el grupo.</p></header>
    <section className="teaching-toolbar"><label>Clase<Select value={classId} onValueChange={(value)=>{setClassId(value);setSelectedStudent("all")}} options={classes.map((c) => ({ value: String(c.id), label: `${c.name} · ${c.student_count} estudiantes` }))}/></label><label>Estudiante<Select value={selectedStudent} onValueChange={setSelectedStudent} options={[{value:"all",label:"Toda la clase"},...roster.map((s)=>({value:String(s.id),label:s.display_name}))]}/></label>{data?.grade_scales?.length ? <label>Escala de calificación<Select value={gradeScaleId} onValueChange={setGradeScaleId} options={[{value:"all",label:"Escala predeterminada"},...data.grade_scales.map((scale)=>({value:String(scale.id),label:scale.name}))]}/></label> : null}<label>Desde<input type="date" value={dateFrom} onChange={(e)=>setDateFrom(e.target.value)}/></label><label>Hasta<input type="date" value={dateTo} onChange={(e)=>setDateTo(e.target.value)}/></label><span>{data ? `Actualizado ${new Date(data.updated_at).toLocaleTimeString()}` : "Selecciona una clase para comenzar"}</span><Button variant="outline" onClick={() => void refresh()}><RefreshCw size={15}/> Actualizar</Button></section>
    {data && <>
      <section className="teaching-metrics">{[["Estudiantes",metrics?.students??0],["Retos iniciados",metrics?.started??0],["Retos resueltos",metrics?.completed??0],["Intentos",metrics?.attempts??0],["Pistas",metrics?.hints??0],["Finalización",`${metrics?.completion_rate??0}%`],["Tiempo medio",`${Math.round((metrics?.mean_completion_seconds??0)/60)} min`]].map(([label,value])=><article key={String(label)}><span>{label}</span><strong>{value}</strong></article>)}</section>
      <div className="teaching-panels"><section className="teaching-panel"><header><div><p className="page-eyebrow">AULA EN VIVO</p><h2>Investigaciones activas</h2></div><span className="live-pip"><i/> Actualiza cada 30 s</span></header>{live.length ? <div className="teaching-live-list">{live.map((row) => <article key={`${row.student_id}-${row.challenge}`}><div><strong>{row.student}</strong><small>{row.challenge}</small></div><span>{Math.floor(row.elapsed_seconds/60)} min</span><span>{row.attempts} intentos</span><span>{row.hints} pistas</span><span>{row.score} XP</span></article>)}</div> : <p className="teaching-muted"><Activity size={16}/> No hay retos en curso en este momento.</p>}</section>
      <section className="teaching-panel"><header><div><p className="page-eyebrow">RESULTADOS DE PRÁCTICA</p><h2>Actividad por estudiante</h2></div><div className="teaching-exports">{["csv","xlsx","pdf"].map((format)=><a key={format} href={`/api/v1/teaching/export?${new URLSearchParams({class_id:classId,format,...(selectedStudent!=="all"?{student_id:selectedStudent}:{}),...(gradeScaleId!=="all"?{grade_scale_id:gradeScaleId}:{}),...(dateFrom?{date_from:`${dateFrom}T00:00:00`}:{}),...(dateTo?{date_to:`${dateTo}T23:59:59`}:{})})}`}><ArrowDownToLine size={13}/>{format.toUpperCase()}</a>)}</div></header><div className="teaching-table-wrap"><table><thead><tr><th>Estudiante</th><th>Iniciados</th><th>Resueltos</th><th>Intentos</th><th>Pistas</th><th>Puntaje</th><th>Nota</th><th>Última actividad</th></tr></thead><tbody>{data.students.map((s)=><tr key={s.student_id}><td><button className="teaching-student-link" onClick={()=>void showStudent(s.student_id)}>{s.display_name}</button></td><td>{s.started}</td><td>{s.completed}</td><td>{s.attempts}</td><td>{s.hints}</td><td>{s.score} XP</td><td>{s.grade?.value ?? "—"}</td><td>{s.last_activity?new Date(s.last_activity).toLocaleString():"—"}</td></tr>)}</tbody></table>{!data.students.length&&<p className="teaching-muted"><Users size={16}/> Aún no hay estudiantes inscritos.</p>}</div></section>
      <section className="teaching-panel"><header><div><p className="page-eyebrow">RETOS QUE REQUIEREN ATENCIÓN</p><h2>Señales para orientar la clase</h2></div></header><div className="teaching-challenge-list">{data.challenging.map((c)=><article key={c.challenge_id}><strong>{c.title}</strong><span>{c.failures} respuestas incorrectas</span><span>{c.abandoned} sin actividad reciente</span><span>{c.completed} de {c.started} iniciados resueltos</span></article>)}</div></section>
      <section className="teaching-panel"><header><div><p className="page-eyebrow">COMUNICACIÓN DEL CURSO</p><h2>Avisos para tu clase</h2></div><BellRing size={18}/></header><form className="teaching-announcement-form" onSubmit={(e)=>void createAnnouncement(e)}><Input value={title} onChange={(e)=>setTitle(e.target.value)} placeholder="Título del aviso" maxLength={180}/><textarea value={content} onChange={(e)=>setContent(e.target.value)} placeholder="Escribe una orientación o recordatorio para el grupo…" maxLength={10000}/><label>Publicar <input type="datetime-local" value={publishAt} onChange={(e)=>setPublishAt(e.target.value)}/><small>Déjalo vacío para publicar ahora.</small></label><Button type="submit" disabled={busy||!title.trim()||!content.trim()}>{busy?"Guardando…":"Guardar aviso"}</Button></form><div className="teaching-announcements">{announcements.map((n)=><article key={n.id} className={n.archived_at?"archived":""}><div><strong>{n.title}</strong><small>{n.archived_at?"Archivado":new Date(n.publish_at).toLocaleString()}</small><p>{n.content_markdown}</p></div>{!n.archived_at&&<Button variant="quiet" onClick={()=>void archive(n.id)}>Archivar</Button>}</article>)}</div></section></div>
      {studentDetail&&<div className="teaching-modal-backdrop" onClick={()=>setStudentDetail(null)}><section className="teaching-modal" onClick={(e)=>e.stopPropagation()}><button className="teaching-modal-close" onClick={()=>setStudentDetail(null)}>Cerrar ×</button><p className="page-eyebrow">HISTORIAL INDIVIDUAL</p><h2>{studentDetail.student.display_name}</h2><p>{studentDetail.student.completed} retos resueltos · {studentDetail.student.score} XP</p>{studentDetail.history.map((h,i)=><article key={`${h.created_at}-${i}`}><strong>{h.challenge}</strong><span>{h.type} · {h.points} XP</span><small>{new Date(h.created_at).toLocaleString()}</small></article>)}</section></div>}
    </>}
  </div>;
}
