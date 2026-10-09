# Guía Práctica de Despliegue 24/7 para Zero

Esta guía te explica cómo poner **Zero** a funcionar en internet de forma **permanente, segura y 100% independiente de tu computadora**.

---

## 🌟 Opción 1 (La más fácil y rápida — Sin saber de servidores)
### Usar Render.com o Railway

No necesitas comprar dominio ni configurar servidores Linux. La plataforma te da un enlace web seguro (`https://tu-sistema.onrender.com`) accesible desde cualquier teléfono, tablet o computadora del mundo.

### Pasos:
1. **Crear una cuenta:**
   - Entra en [Render.com](https://render.com/) o [Railway.app](https://railway.app/) y regístrate gratis con tu cuenta de Google o GitHub.
2. **Subir el código:**
   - En tu cuenta de GitHub, crea un repositorio privado llamado `zero`.
   - Sube la carpeta del proyecto a ese repositorio.
3. **Crear el servicio en Render:**
   - En Render, haz clic en **New + → Web Service**.
   - Selecciona tu repositorio de GitHub.
   - En **Environment**, elige **Docker** (detectará automáticamente el archivo `Dockerfile` y `render.yaml` que ya te dejé preparados).
   - En **Disks (Almacenamiento persistente)**, añade un disco llamado `zero-data` con punto de montaje `/app/data` (1 GB es más que suficiente).
4. **Listo:** En 2 minutos tendrás tu enlace web activo 24/7 con certificado de seguridad SSL.

---

## 🚀 Opción 2 (Servidor propio VPS — Máximo control y profesionalismo)
### Usar DigitalOcean o Hetzner ($4 a $6 USD al mes)

Te da una máquina virtual dedicada en la nube con su propia dirección IP fija y la posibilidad de usar tu propio dominio (ej. `gestion.tuempresa.com`).

### Pasos:
1. **Crear el servidor:**
   - Entra a [DigitalOcean.com](https://digitalocean.com) (o Hetzner Cloud).
   - Crea un **Droplet** con:
     - Sistema Operativo: **Ubuntu 22.04 LTS** o **24.04 LTS**.
     - Plan: Básico ($4 o $6 USD/mes con 1 GB RAM y 25 GB SSD).
     - Ubicación: Nueva York o Miami (la más cercana a República Dominicana / Latinoamérica).
2. **Conectarte al servidor:**
   - Desde la terminal de tu Mac, escribe:
     ```sh
     ssh root@TU_IP_DEL_SERVIDOR
     ```
3. **Ejecutar el instalador automático:**
   - Copia y pega este único comando en el servidor:
     ```sh
     bash despliegue_vps.sh
     ```
     *(Si tienes un dominio como `app.miempresa.com`, puedes ponerlo así: `bash despliegue_vps.sh app.miempresa.com` y configurará HTTPS automáticamente).*
4. **Listo:**
   - El script configura el sistema para que nunca se apague, instala respaldos automáticos a las 3:00 AM y levanta el servidor web seguro.

---

## 💾 ¿Y mis datos actuales?
Para llevarte tus datos existentes (empresas, clientes, facturas, personal y nóminas):
1. Copia tu archivo actual `data/zero.sqlite3` a la carpeta `data/` del servidor en la nube.
2. O simplemente entra a tu nuevo Zero en la nube, ve a **Importar empresa** y sube el archivo `.zero.json` exportado desde tu Mac.
