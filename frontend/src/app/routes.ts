import { Activity, BookMarked, BookOpen, ChartNoAxesCombined, CircleHelp, FileText, GraduationCap, ScrollText, Settings, Shield, Trophy, Users, UserRoundCog, Library, type LucideIcon } from 'lucide-react'

/** `student` entries are the learner journey; staff design the same content from the teaching screens. */
export type AppRoute = { path: string; label: string; description: string; permission?: string; icon: LucideIcon; audience?: 'student' }
export const routes: AppRoute[] = [
  { path: '/workspace', label: 'Mi espacio', description: 'Resumen de tu actividad de aprendizaje.', icon: BookOpen },
  { path: '/learn', label: 'Aprender', description: 'Lecciones y actividades de tu curso.', permission: 'course.view', icon: Library, audience: 'student' },
  { path: '/challenges', label: 'Retos', description: 'Prácticas de seguridad para resolver.', permission: 'challenge.view', icon: Shield, audience: 'student' },
  { path: '/events', label: 'Eventos', description: 'Competiciones y ejercicios de clase.', permission: 'event.view', icon: Activity, audience: 'student' },
  { path: '/scoreboard', label: 'Marcador', description: 'Posiciones y puntuación del campus.', permission: 'scoreboard.view', icon: Trophy },
  { path: '/teaching/curriculum', label: 'Currículo', description: 'Cursos, módulos, lecciones y actividades.', permission: 'course.manage', icon: BookMarked },
  { path: '/teaching/ctf', label: 'Diseñar CTF', description: 'Crea retos y organiza competencias para tus clases.', permission: 'event.manage', icon: Shield },
  { path: '/teaching/importer', label: 'Importar retos', description: 'Carga paquetes de retos revisados y validados.', permission: 'challenge.create', icon: FileText },
  { path: '/teaching/analytics', label: 'Seguimiento docente', description: 'Avances, actividad en aula y comunicación con tus clases.', permission: 'event.manage', icon: ChartNoAxesCombined },
  { path: '/classes', label: 'Clases', description: 'Grupos y miembros del campus.', permission: 'class.view', icon: GraduationCap },
  { path: '/users', label: 'Personas', description: 'Estudiantes y profesores.', permission: 'user.view', icon: Users },
  { path: '/settings', label: 'Configuración', description: 'Preferencias del sistema.', permission: 'settings.view', icon: Settings },
  { path: '/roles', label: 'Roles', description: 'Permisos de acceso al campus.', permission: 'role.view', icon: UserRoundCog },
  { path: '/audit', label: 'Bitácora', description: 'Registro de cambios del sistema.', permission: 'audit.view', icon: ScrollText },
  { path: '/help', label: 'Ayuda', description: 'Cómo orientarte en Cyberlab.', icon: CircleHelp },
]
