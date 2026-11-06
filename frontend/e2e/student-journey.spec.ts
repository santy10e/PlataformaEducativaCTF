import { expect, request, test, type APIRequestContext } from '@playwright/test'

// Runs against a real, seeded stack (see `make e2e`). Nothing here is mocked.
const username = process.env.CYBERLAB_E2E_USERNAME
const password = process.env.CYBERLAB_E2E_PASSWORD
const baseURL = process.env.CYBERLAB_E2E_BASE_URL ?? 'http://127.0.0.1:5174'

async function adminApi(): Promise<{ api: APIRequestContext; csrf: string }> {
  const api = await request.newContext({ baseURL })
  const login = await api.post('/api/v1/auth/login', { data: { username, password } })
  expect(login.ok(), await login.text()).toBe(true)
  return { api, csrf: (await login.json()).csrf_token }
}

async function call(api: APIRequestContext, csrf: string, method: 'post' | 'put', path: string, data: unknown) {
  const response = await api[method](path, { data, headers: { 'x-csrf-token': csrf } })
  expect(response.ok(), `${method.toUpperCase()} ${path}: ${await response.text()}`).toBe(true)
  return response.json()
}

test('un estudiante resuelve en el navegador un reto preparado por la administración', async ({ page }) => {
  test.skip(!username || !password, 'Define CYBERLAB_E2E_USERNAME y CYBERLAB_E2E_PASSWORD (cuenta ADMIN) para el recorrido real.')
  const run = Date.now().toString(36)
  const { api, csrf } = await adminApi()
  const schoolClass = await call(api, csrf, 'post', '/api/v1/classes', { name: `E2E ${run}`, academic_period: '2026' })
  const temporary = `Temporal-${run}-Pass!`
  await call(api, csrf, 'post', '/api/v1/users', { username: `e2e.${run}`, password: temporary, first_name: 'Prueba', last_name: run, role: 'STUDENT', class_ids: [schoolClass.id] })
  const categories = await (await api.get('/api/v1/ctf/categories')).json()
  const difficulties = await (await api.get('/api/v1/ctf/difficulties')).json()
  const event = await call(api, csrf, 'post', '/api/v1/ctf/events', { name: `Evento E2E ${run}`, status: 'PUBLISHED', class_ids: [schoolClass.id] })
  const body = { category_id: categories[0].id, difficulty_id: difficulties[0].id, slug: `e2e-${run}`, title: `Reto E2E ${run}`, description_markdown: 'Busca la **bandera**.', points: 100, status: 'DRAFT' }
  const challenge = await call(api, csrf, 'post', `/api/v1/ctf/events/${event.id}/challenges`, body)
  await call(api, csrf, 'post', `/api/v1/ctf/events/${event.id}/challenges/${challenge.id}/flags`, { strategy: 'STATIC', value: `CYBERLAB{e2e_${run}}` })
  await call(api, csrf, 'post', `/api/v1/ctf/events/${event.id}/challenges/${challenge.id}/hints`, { order: 1, cost: 10, content_markdown: 'Pista E2E visible' })
  await call(api, csrf, 'put', `/api/v1/ctf/events/${event.id}/challenges/${challenge.id}`, { ...body, status: 'PUBLISHED' })
  await api.dispose()

  // First login with the temporary password must end on the password change screen.
  await page.goto('/login')
  await page.getByLabel('Usuario').fill(`e2e.${run}`)
  await page.getByLabel('Contraseña').fill(temporary)
  await page.getByRole('button', { name: /entrar al campus/i }).click()
  await expect(page.getByRole('heading', { name: 'Elige tu propia llave.' })).toBeVisible()
  await page.getByLabel('Contraseña temporal').fill(temporary)
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(`Definitiva-${run}-Pass!`)
  await page.getByLabel('Confirma la nueva contraseña').fill(`Definitiva-${run}-Pass!`)
  await page.getByRole('button', { name: /actualizar contraseña/i }).click()
  await expect(page.getByRole('heading', { name: 'Hola, Prueba.' })).toBeVisible()

  await page.goto(`/study/events/${event.public_id}/challenges/${challenge.public_id}`)
  await expect(page.getByRole('heading', { name: `Reto E2E ${run}` })).toBeVisible()
  await page.getByRole('button', { name: /iniciar reto/i }).click()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: /desbloquear pista/i }).click()
  await expect(page.getByText('Pista E2E visible')).toBeVisible()

  const answer = page.getByPlaceholder('CYBERLAB{…}')
  await answer.fill('CYBERLAB{equivocada}')
  await page.getByRole('button', { name: /enviar respuesta/i }).click()
  await expect(page.getByText(/no coincide/i)).toBeVisible()
  await answer.fill(`CYBERLAB{e2e_${run}}`)
  await page.getByRole('button', { name: /enviar respuesta/i }).click()
  await expect(page.getByText('Reto resuelto')).toBeVisible()
  const expected = Math.round(100 * categories[0].multiplier * difficulties[0].multiplier)
  await expect(page.getByText(`+${expected} XP`)).toBeVisible()
})
