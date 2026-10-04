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
- La interfaz y tipografías se sirven desde los contenedores; no necesitan una conexión a Internet en tiempo de ejecución. Descargar/actualizar imágenes sí requiere acceso al registro Docker.
