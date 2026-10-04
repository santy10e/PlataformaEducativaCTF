import { expect, test } from '@playwright/test'

const username = process.env.CYBERLAB_E2E_USERNAME
const password = process.env.CYBERLAB_E2E_PASSWORD

test('la sesión real permite entrar al espacio y cerrarla', async ({ page }) => {
  test.skip(!username || !password, 'Define CYBERLAB_E2E_USERNAME y CYBERLAB_E2E_PASSWORD para el smoke local.')
  await page.goto('/login')
  await page.getByLabel('Usuario').fill(username!)
  await page.getByLabel('Contraseña').fill(password!)
  await page.getByRole('button', { name: /entrar al campus/i }).click()
  await expect(page.getByRole('heading', { name: /hola,/i })).toBeVisible()
  await expect(page.getByText('SESIÓN CIFRADA')).toBeVisible()
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible()
})
