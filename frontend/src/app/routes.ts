import { Activity, BookOpen, ChartNoAxesCombined, CircleHelp, FileText, GraduationCap, ScrollText, Settings, Shield, Users, UserRoundCog, type LucideIcon } from 'lucide-react'

export type AppRoute = { path: string; label: string; description: string; permission?: string; icon: LucideIcon; phase: number }
export const routes: AppRoute[] = [
  { path: '/workspace', label: 'Mi espacio', description: 'Resumen de tu actividad de aprendizaje.', icon: BookOpen, phase: 2 },
  { path: '/challenges', label: 'Retos', description: 'Prácticas de seguridad para resolver.', permission: 'challenge.view', icon: Shield, phase: 4 },
  { path: '/events', label: 'Eventos', description: 'Competiciones y ejercicios de clase.', permission: 'event.view', icon: Activity, phase: 4 },
  { path: '/scoreboard', label: 'Marcador', description: 'Posiciones y puntuación del campus.', permission: 'scoreboard.view', icon: Activity, phase: 7 },
  { path: '/teaching/ctf', label: 'Diseñar CTF', description: 'Crea retos y organiza competencias para tus clases.', permission: 'event.manage', icon: Shield, phase: 6 },
  { path: '/teaching/importer', label: 'Importar retos', description: 'Carga paquetes de retos revisados y validados.', permission: 'challenge.create', icon: FileText, phase: 9 },
  { path: '/teaching/analytics', label: 'Seguimiento docente', description: 'Avances, actividad en aula y comunicación con tus clases.', permission: 'event.manage', icon: ChartNoAxesCombined, phase: 8 },
  { path: '/classes', label: 'Clases', description: 'Grupos y miembros del campus.', permission: 'class.view', icon: GraduationCap, phase: 3 },
  { path: '/users', label: 'Personas', description: 'Estudiantes y profesores.', permission: 'user.view', icon: Users, phase: 3 },
  { path: '/resources', label: 'Recursos', description: 'Guías y material de referencia.', icon: FileText, phase: 7 },
  { path: '/settings', label: 'Configuración', description: 'Preferencias del sistema.', permission: 'settings.view', icon: Settings, phase: 2 },
  { path: '/roles', label: 'Roles', description: 'Permisos de acceso al campus.', permission: 'role.view', icon: UserRoundCog, phase: 1 },
  { path: '/audit', label: 'Bitácora', description: 'Registro de cambios del sistema.', permission: 'audit.view', icon: ScrollText, phase: 1 },
  { path: '/help', label: 'Ayuda', description: 'Cómo orientarte en Cyberlab.', icon: CircleHelp, phase: 2 },
]
