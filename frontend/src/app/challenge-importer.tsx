import { useEffect, useState } from "react";
import { Download, FileArchive, RotateCw, Upload } from "lucide-react";
import { api, unwrap } from "../api/client";
import { Button, Select, toast } from "../components/ui";

type EventRow = { id:number; name:string; status:string };
type Issue = { file:string; field:string; message:string };
type Preview = { valid:boolean; name?:string; count?:number; warnings:Issue[]; errors?:Issue[]; challenges:Array<{manifest:string;slug:string;title:string;category:string;difficulty:string;points:number;status_after_import:string;action:string;hints:number;files:number}> };

function csrfToken(): string {
  return decodeURIComponent(document.cookie.split("; ").find((item)=>item.startsWith("cyberlab_csrf="))?.split("=").slice(1).join("=") ?? "");
}

async function sendArchive(eventId:number, action:"preview"|"confirm", archive:File) {
  const response = await fetch(`/api/v1/ctf/events/${eventId}/import/${action}`, {
    method:"POST", credentials:"include", headers:{"Content-Type":"application/zip","X-CSRF-Token":csrfToken()}, body:archive,
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result?.error?.message ?? "No se pudo procesar el paquete.");
  return result;
}

export function ChallengeImporterPage() {
  const [eventId,setEventId] = useState("");
  const [archive,setArchive] = useState<File|null>(null);
  const [preview,setPreview] = useState<Preview|null>(null);
  const [busy,setBusy] = useState(false);
  const [events,setEvents] = useState<EventRow[]>([]);
  useEffect(()=>{void api.GET("/api/v1/ctf/events",{params:{query:{page:1,page_size:100}}}).then(unwrap).then((value)=>setEvents((value as {items:EventRow[]}).items)).catch((error:Error)=>toast(error.message));},[]);

  async function inspect() {
    if (!archive || !eventId) return;
    setBusy(true);
    try { setPreview(await sendArchive(Number(eventId),"preview",archive) as Preview); }
    catch (error) { toast(error instanceof Error ? error.message : "No se pudo validar el ZIP."); }
    finally { setBusy(false); }
  }

  async function confirm() {
    if (!archive || !eventId || !preview?.valid) return;
    setBusy(true);
    try {
      const result = await sendArchive(Number(eventId),"confirm",archive) as {created:number;updated:number};
      toast(`Importación lista: ${result.created} creados, ${result.updated} actualizados.`);
      setPreview(null); setArchive(null);
    } catch (error) { toast(error instanceof Error ? error.message : "No se pudo confirmar la importación."); }
    finally { setBusy(false); }
  }

  return <div className="challenge-importer">
    <div className="workspace-edition"><span>DOCENCIA &nbsp;/&nbsp; BIBLIOTECA DE RETOS</span><span>FASE 09</span></div>
    <header className="workspace-page-heading"><p className="page-eyebrow">PAQUETES PORTABLES · YAML + ZIP</p><h1>Importar una práctica</h1><p>Revisa el contenido antes de incorporarlo. Los retos importados quedan como borradores.</p></header>
    <section className="import-card">
      <div className="import-steps"><span className={!preview?"active":"done"}>01 · Subir</span><span className={preview?"active":""}>02 · Revisar</span><span>03 · Confirmar</span></div>
      <label>Evento de destino<Select value={eventId} onValueChange={(value)=>{setEventId(value);setPreview(null)}} options={events.map((item)=>({value:String(item.id),label:`${item.name} · ${item.status}`}))}/></label>
      <label className="import-file-picker"><FileArchive size={24}/><strong>{archive?.name ?? "Selecciona un ZIP con challenge.yml o ctf.yml"}</strong><small>Hasta 20 MB comprimido; archivos adjuntos de hasta 10 MB.</small><input type="file" accept=".zip,application/zip" onChange={(event)=>{setArchive(event.target.files?.[0] ?? null);setPreview(null)}}/></label>
      <div className="import-actions"><Button variant="outline" disabled={busy||!eventId||!archive} onClick={()=>void inspect()}><Upload size={15}/>{busy?"Validando…":"Validar paquete"}</Button><Button disabled={busy||!preview?.valid} onClick={()=>void confirm()}><RotateCw size={15}/>{busy?"Importando…":"Confirmar como borrador"}</Button></div>
    </section>
    {preview&&<section className="import-card import-review"><header><div><p className="page-eyebrow">INFORME DE VALIDACIÓN</p><h2>{preview.name ?? "Paquete sin nombre"}</h2></div><strong>{preview.valid?`${preview.count} retos`:`${preview.errors?.length ?? 0} errores`}</strong></header>
      {preview.errors?.map((issue,index)=><article className="import-issue error" key={`${issue.file}-${issue.field}-${index}`}><strong>{issue.file||"Paquete"} · {issue.field}</strong><span>{issue.message}</span></article>)}
      {preview.warnings.map((issue,index)=><article className="import-issue warning" key={`${issue.file}-${issue.field}-${index}`}><strong>{issue.file||"Paquete"} · {issue.field}</strong><span>{issue.message}</span></article>)}
      {preview.challenges.map((challenge)=><article className="import-challenge-row" key={challenge.slug}><div><strong>{challenge.title}</strong><small>{challenge.slug} · {challenge.category} · {challenge.difficulty}</small></div><span>{challenge.points} pts</span><span>{challenge.action === "update"?"Actualizar":"Crear"} como borrador</span><small>{challenge.hints} pistas · {challenge.files} archivos</small></article>)}
    </section>}
    <section className="import-card"><p className="page-eyebrow">EXPORTAR PAQUETES</p><h2>Descarga para respaldar o compartir</h2><div className="import-export-list">{events.map((item)=><article key={item.id}><strong>{item.name}</strong><a href={`/api/v1/ctf/events/${item.id}/export`}><Download size={14}/> Evento ZIP</a></article>)}</div></section>
  </div>;
}
