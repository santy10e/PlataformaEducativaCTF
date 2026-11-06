# Red y servicios

```text
Navegador de la red institucional
              │ HTTP :80 (Compose base)
            Nginx
          ┌───┴────┐
   frontend:80   backend:8000
                    │ red db interna
                  mysql:3306
```

- Solo Nginx publica un puerto del host (`80:80`). El frontend y la API no publican puertos directamente.
- MySQL está en una red Docker `internal`; solo backend puede conectarse a `mysql:3306`.
- `challenge_files` persiste adjuntos del reto; `mysql_data` persiste la base de datos.
- El endpoint de salud es `/api/v1/health` y comprueba la conexión con MySQL.
- El límite del proxy API es 21 MB para permitir importaciones ZIP acotadas. El servicio no debe exponerse directamente a Internet.
- Para HTTPS, configura un gateway inverso institucional delante de Nginx. Debe sobrescribir `X-Forwarded-Proto`, preservar `Host` y no aceptar ese encabezado arbitrariamente de clientes. Nginx pasa el protocolo recibido a la API para que esta marque las cookies `Secure`.
- Nginx reemplaza `X-Forwarded-For` por la dirección real del cliente (`$remote_addr`) y la API solo recibe ese encabezado desde la red interna. Así el límite de intentos de login y de envíos se aplica por equipo y no por proxy. Con Docker Desktop (Windows/macOS) todas las conexiones pueden llegar desde la misma dirección NAT; en Linux se conserva la IP de cada equipo. Si hay un gateway TLS delante, configura en Nginx `set_real_ip_from` con la IP del gateway para recuperar la del cliente.
- La interfaz y tipografías se sirven desde los contenedores; no necesitan una conexión a Internet en tiempo de ejecución. Descargar/actualizar imágenes sí requiere acceso al registro Docker.
