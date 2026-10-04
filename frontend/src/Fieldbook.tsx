import {
  ArrowDownRight,
  ArrowRight,
  AudioLines,
  BookOpen,
  Circle,
  Crosshair,
  LockKeyhole,
  MoveUpRight,
  Orbit,
  ScanLine,
} from "lucide-react";
import "./fieldbook.css";

const notes = [
  {
    no: "01",
    name: "La pista en el encabezado",
    type: "ANÁLISIS WEB",
    time: "12 MIN",
    tone: "paper-red",
  },
  {
    no: "02",
    name: "Ecos en la red",
    type: "ANÁLISIS DE RED",
    time: "18 MIN",
    tone: "paper-blue",
  },
  {
    no: "03",
    name: "Un archivo fuera de lugar",
    type: "FORENSE DIGITAL",
    time: "20 MIN",
    tone: "paper-olive",
  },
];

export function Fieldbook() {
  return (
    <main className="fieldbook">
      <header className="fb-nav">
        <a className="fb-identity" href="/">
          <span className="fb-signet">
            <Crosshair size={18} />
          </span>
          <span>
            CYBERLAB<small>CUADERNOS DE CAMPO · VOL. 01</small>
          </span>
        </a>
        <nav>
          <a className="fb-current" href="#portada">
            Cuaderno
          </a>
          <a href="#practicas">Prácticas</a>
          <a href="#metodo">El método</a>
        </nav>
        <a className="fb-account" href="/login">
          <span className="fb-avatar">↗</span>
          <span>Entrar al campus</span>
          <MoveUpRight size={13} />
        </a>
      </header>

      <section className="fb-cover" id="portada">
        <div className="fb-cover-copy">
          <div className="fb-edition">
            <span>CUADERNO 01</span>
            <i /> SEMESTRE II · 2029
          </div>
          <p className="fb-kicker">LABORATORIO ABIERTO DE CIBERSEGURIDADs</p>
          <h1>
            La curiosidad
            <br />
            es una <em>herramienta.</em>
          </h1>
          <p className="fb-intro">
            Un lugar para mirar más de cerca, hacer buenas preguntas y aprender
            seguridad digital resolviendo problemas reales.
          </p>
          <a className="fb-start" href="#practicas">
            <span>Abrir el cuaderno</span>
            <ArrowDownRight size={17} />
          </a>
          <p className="fb-handwritten">Empieza por lo que no encaja.</p>
        </div>
        <div
          className="fb-plate"
          aria-label="Ilustración de una señal digital bajo análisis"
        >
          <div className="plate-index">
            LÁMINA A <span>FIG. 01 — SEÑAL / RUIDO</span>
          </div>
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit orbit-three" />
          <div className="plate-core">
            <LockKeyhole size={27} />
            <span>OBSERVAR</span>
          </div>
          <i className="node node-a" />
          <i className="node node-b" />
          <i className="node node-c" />
          <i className="node node-d" />
          <div className="plate-wave">
            <AudioLines size={23} />
            <span>
              10110<span className="wave-dash">—</span>01001
            </span>
          </div>
          <div className="plate-callout callout-a">
            <span>A</span> PUNTO DE ORIGEN
          </div>
          <div className="plate-callout callout-b">
            <span>B</span> RASTRO ENCONTRADO
          </div>
          <div className="plate-coordinates">
            04° 39' N&nbsp; · &nbsp;74° 06' O<br />
            TRAZA LOCALIZADA
          </div>
          <div className="plate-scale">
            <span>0</span>
            <i />
            <span>1.0 ms</span>
          </div>
          <Orbit className="plate-orbit-icon" size={17} />
        </div>
        <div className="fb-cover-foot">
          <span>APRENDER HACIENDO / BOGOTÁ, COLOMBIA</span>
          <span>
            01 &nbsp;—&nbsp; 12 <i />
          </span>
        </div>
      </section>

      <section className="fb-practice" id="practicas">
        <div className="fb-section-top">
          <p>
            <span>01</span> EL TRABAJO DE HOY
          </p>
          <p>CAMPO DE PRÁCTICA &nbsp; / &nbsp; NIVEL INICIAL</p>
        </div>
        <div className="fb-practice-intro">
          <h2>
            Aprender a ver
            <br />
            lo que <em>otros pasan por alto.</em>
          </h2>
          <p>
            Cada práctica es una pequeña investigación. Sigue las señales, toma
            notas y llega a tus propias conclusiones.
          </p>
        </div>
        <div className="fb-notes">
          {notes.map((note) => (
            <a className="fb-note" href="#metodo" key={note.no}>
              <div className={`note-art ${note.tone}`}>
                <span className="note-corner">CY / {note.no}</span>
                {note.no === "01" ? (
                  <>
                    <ScanLine size={49} />
                    <i />
                  </>
                ) : note.no === "02" ? (
                  <>
                    <div className="signal-line" />
                    <AudioLines size={42} />
                    <div className="signal-line short" />
                  </>
                ) : (
                  <>
                    <BookOpen size={42} />
                    <Circle size={19} />
                  </>
                )}
              </div>
              <div className="note-meta">
                <span>{note.type}</span>
                <span>{note.time} &nbsp; ↗</span>
              </div>
              <h3>
                <span>{note.no}</span>
                {note.name}
                <ArrowRight size={16} />
              </h3>
            </a>
          ))}
        </div>
        <div className="fb-all-notes">
          <span>NO NECESITAS SABERLO TODO. SOLO EMPEZAR.</span>
          <a href="#metodo">
            Ver todas las prácticas <ArrowRight size={15} />
          </a>
        </div>
      </section>

      <footer className="fb-footer" id="metodo">
        <span>
          CYBERLAB <i>×</i> APRENDER · EXPLORAR · COMPARTIR
        </span>
        <span>
          HECHO PARA MENTES INQUIETAS <ArrowRight size={13} />
        </span>
      </footer>
    </main>
  );
}
