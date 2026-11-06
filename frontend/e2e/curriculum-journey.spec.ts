import { expect, request, test, type Page } from '@playwright/test'

// SPEC §17 criterion 3: a teacher builds course → module → lesson → activity only from the UI,
// and a learner of the assigned class completes it. Runs against a real, seeded stack (`make e2e`).
const username = process.env.CYBERLAB_E2E_USERNAME
const password = process.env.CYBERLAB_E2E_PASSWORD
const baseURL = process.env.CYBERLAB_E2E_BASE_URL ?? 'http://127.0.0.1:5174'

async function pick(page: Page, label: string, option: string) {
  await page.locator('form.cur-editor label', { hasText: label }).getByRole('combobox').click()
  await page.getByRole('option', { name: option, exact: true }).click()
}

async function firstLogin(page: Page, user: string, temporary: string, final: string) {
  await page.goto('/login')
  await page.getByLabel('Usuario').fill(user)
  await page.getByLabel('Contraseña').fill(temporary)
  await page.getByRole('button', { name: /entrar al campus/i }).click()
  await page.getByLabel('Contraseña temporal').fill(temporary)
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(final)
  await page.getByLabel('Confirma la nueva contraseña').fill(final)
  await page.getByRole('button', { name: /actualizar contraseña/i }).click()
  await expect(page.getByRole('heading', { name: /^Hola,/ })).toBeVisible()
}

test('un docente arma un curso completo desde la interfaz y su estudiante lo completa', async ({ browser }) => {
  test.skip(!username || !password, 'Define CYBERLAB_E2E_USERNAME y CYBERLAB_E2E_PASSWORD (cuenta ADMIN) para el recorrido real.')
  const run = Date.now().toString(36)
  const temporary = `Temporal-${run}-Pass!`
  const admin = await request.newContext({ baseURL })
  const csrf = (await (await admin.post('/api/v1/auth/login', { data: { username, password } })).json()).csrf_token
  const headers = { 'x-csrf-token': csrf }
  const teacher = await (await admin.post('/api/v1/users', { headers, data: { username: `cur.prof.${run}`, password: temporary, first_name: 'Docente', last_name: run, role: 'INSTRUCTOR' } })).json()
  const schoolClass = await (await admin.post('/api/v1/classes', { headers, data: { name: `Aula cur ${run}`, academic_period: '2026', teacher_user_id: teacher.id } })).json()
  const learner = await admin.post('/api/v1/users', { headers, data: { username: `cur.alum.${run}`, password: temporary, first_name: 'Lucía', last_name: run, role: 'STUDENT', class_ids: [schoolClass.id] } })
  expect(learner.ok(), await learner.text()).toBe(true)
  await admin.dispose()

  // ---- teacher, browser only
  const teacherPage = await (await browser.newContext()).newPage()
  await firstLogin(teacherPage, `cur.prof.${run}`, temporary, `Docente-${run}-Pass!`)
  await teacherPage.goto('/teaching/curriculum')
  await teacherPage.getByRole('button', { name: 'Nuevo' }).click()
  await teacherPage.getByLabel('Título del curso').fill(`Curso ${run}`)
  await pick(teacherPage, 'Estado', 'Publicado')
  await teacherPage.getByText(`Aula cur ${run} · 2026`).click()
  await teacherPage.getByRole('button', { name: /guardar curso/i }).click()
  await expect(teacherPage.getByText('Curso guardado.').first()).toBeVisible()

  await teacherPage.getByRole('button', { name: 'Módulo', exact: true }).click()
  await teacherPage.getByLabel('Título del módulo').fill('Mes 1 · Terminal')
  await pick(teacherPage, 'Estado', 'Publicado')
  await teacherPage.getByRole('button', { name: /crear módulo/i }).click()
  await expect(teacherPage.getByText('Módulo creado.').first()).toBeVisible()

  await teacherPage.getByRole('button', { name: 'Lección', exact: true }).click()
  await teacherPage.getByLabel('Título de la lección').fill('Primeros comandos')
  await teacherPage.getByLabel('Contenido de la lección (Markdown)').fill('Usa `ls` para **listar** archivos.')
  await pick(teacherPage, 'Estado', 'Publicado')
  await teacherPage.getByRole('button', { name: /crear lección/i }).click()
  await expect(teacherPage.getByText('Lección creada.').first()).toBeVisible()

  await teacherPage.getByRole('button', { name: 'Actividad', exact: true }).click()
  await pick(teacherPage, 'Tipo de actividad', 'Cuestionario')
  await teacherPage.getByLabel('Título', { exact: true }).fill('Comprueba la lectura')
  await pick(teacherPage, 'Estado', 'Publicado')
  await teacherPage.getByLabel('Enunciado de la pregunta 1').fill('¿Qué comando lista archivos?')
  await teacherPage.getByLabel('Opción 1 de la pregunta 1').fill('ls')
  await teacherPage.getByLabel('Opción 2 de la pregunta 1').fill('cd')
  await teacherPage.getByRole('button', { name: /crear actividad/i }).click()
  await expect(teacherPage.getByText('Actividad creada.').first()).toBeVisible()

  // ---- learner of the assigned class
  const studentPage = await (await browser.newContext()).newPage()
  await firstLogin(studentPage, `cur.alum.${run}`, temporary, `Alumna-${run}-Pass!`)
  await studentPage.goto('/learn')
  const course = studentPage.locator('section.cur-course', { hasText: `Curso ${run}` })
  await course.getByRole('link', { name: /ver temario/i }).click()
  await studentPage.getByRole('link', { name: /Primeros comandos/ }).click()
  await expect(studentPage.getByRole('heading', { name: 'Primeros comandos' })).toBeVisible()
  await expect(studentPage.getByText('listar')).toBeVisible()
  await studentPage.getByLabel('ls').check()
  await studentPage.getByRole('button', { name: /enviar respuestas/i }).click()
  await expect(studentPage.getByText(/Puntuación:/)).toContainText('100')

  // The teacher sees the completion in the progress matrix.
  await teacherPage.getByRole('tab', { name: 'Progreso' }).click()
  await expect(teacherPage.getByRole('row', { name: new RegExp(`Lucía ${run}`) })).toContainText('100%')
})
