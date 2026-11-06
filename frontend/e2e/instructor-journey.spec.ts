import { expect, request, test, type APIRequestContext, type Page } from '@playwright/test'

// Runs against a real, seeded stack (see `make e2e`). The instructor works only through the browser.
const username = process.env.CYBERLAB_E2E_USERNAME
const password = process.env.CYBERLAB_E2E_PASSWORD
const baseURL = process.env.CYBERLAB_E2E_BASE_URL ?? 'http://127.0.0.1:5174'

async function session(user: string, secret: string): Promise<{ api: APIRequestContext; csrf: string }> {
  const api = await request.newContext({ baseURL })
  const login = await api.post('/api/v1/auth/login', { data: { username: user, password: secret } })
  expect(login.ok(), await login.text()).toBe(true)
  return { api, csrf: (await login.json()).csrf_token }
}

async function pick(page: Page, label: string, option: string | RegExp) {
  await page.locator('label', { hasText: label }).getByRole('combobox').click()
  await page.getByRole('option', { name: option }).first().click()
}

test('un docente crea y publica un reto desde el panel y su estudiante lo resuelve', async ({ page }) => {
  test.skip(!username || !password, 'Define CYBERLAB_E2E_USERNAME y CYBERLAB_E2E_PASSWORD (cuenta ADMIN) para el recorrido real.')
  const run = Date.now().toString(36)
  const temporary = `Temporal-${run}-Pass!`
  const admin = await session(username!, password!)
  const headers = { 'x-csrf-token': admin.csrf }
  const teacher = await (await admin.api.post('/api/v1/users', { headers, data: { username: `prof.${run}`, password: temporary, first_name: 'Docente', last_name: run, role: 'INSTRUCTOR' } })).json()
  const schoolClass = await (await admin.api.post('/api/v1/classes', { headers, data: { name: `Aula ${run}`, academic_period: '2026', teacher_user_id: teacher.id } })).json()
  const learner = await admin.api.post('/api/v1/users', { headers, data: { username: `alum.${run}`, password: temporary, first_name: 'Alumna', last_name: run, role: 'STUDENT', class_ids: [schoolClass.id] } })
  expect(learner.ok(), await learner.text()).toBe(true)
  await admin.api.dispose()

  await page.goto('/login')
  await page.getByLabel('Usuario').fill(`prof.${run}`)
  await page.getByLabel('Contraseña').fill(temporary)
  await page.getByRole('button', { name: /entrar al campus/i }).click()
  await page.getByLabel('Contraseña temporal').fill(temporary)
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(`Docente-${run}-Pass!`)
  await page.getByLabel('Confirma la nueva contraseña').fill(`Docente-${run}-Pass!`)
  await page.getByRole('button', { name: /actualizar contraseña/i }).click()
  await expect(page.getByRole('heading', { name: /Hola, Docente/ })).toBeVisible()

  await page.goto('/teaching/ctf')
  await page.getByRole('button', { name: 'Crear evento' }).click()
  await page.getByLabel('Nombre de la práctica').fill(`Práctica ${run}`)
  await page.locator('label', { hasText: 'Clases asignadas' }).locator('select').selectOption(String(schoolClass.id))
  await page.getByRole('button', { name: /guardar y añadir reto/i }).click()

  await page.getByLabel('Título del reto').fill(`Cabecera ${run}`)
  await pick(page, 'Categoría', 'Web')
  await pick(page, 'Dificultad', 'Inicial')
  await pick(page, 'Estado del reto', 'Publicado')
  await page.getByPlaceholder('CYBERLAB{...}').fill(`CYBERLAB{prof_${run}}`)
  await page.getByRole('button', { name: /guardar reto/i }).click()
  await expect(page.getByText('Reto guardado en el evento.')).toBeVisible()

  const row = page.locator('article, li, div').filter({ hasText: `Práctica ${run}` }).filter({ has: page.getByRole('button', { name: /publicar/i }) }).last()
  await row.getByRole('button', { name: /publicar/i }).click()
  await expect(page.getByText('Evento publicado.')).toBeVisible()

  // The learner sees exactly what the teacher built, and the flag typed in the form is the one that scores.
  const student = await session(`alum.${run}`, temporary)
  const change = await student.api.post('/api/v1/auth/change-password', { headers: { 'x-csrf-token': student.csrf }, data: { current_password: temporary, new_password: `Alumna-${run}-Pass!` } })
  expect(change.ok()).toBe(true)
  const fresh = await session(`alum.${run}`, `Alumna-${run}-Pass!`)
  const events = await (await fresh.api.get('/api/v1/ctf/student/events')).json()
  const event = events.find((item: { name: string }) => item.name === `Práctica ${run}`)
  expect(event).toBeTruthy()
  const challenges = await (await fresh.api.get(`/api/v1/ctf/student/events/${event.public_id}/challenges`)).json()
  expect(challenges.map((item: { title: string }) => item.title)).toEqual([`Cabecera ${run}`])
  const h = { 'x-csrf-token': fresh.csrf }
  expect((await fresh.api.post(`/api/v1/ctf/challenges/${challenges[0].public_id}/start`, { headers: h })).ok()).toBe(true)
  const solved = await (await fresh.api.post(`/api/v1/ctf/challenges/${challenges[0].public_id}/submit`, { headers: h, data: { flag: `CYBERLAB{prof_${run}}` } })).json()
  expect(solved.correct).toBe(true)
  await fresh.api.dispose()
  await student.api.dispose()
})
