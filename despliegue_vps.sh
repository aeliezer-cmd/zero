#!/bin/bash
# ==============================================================================
# Script de Despliegue Automatizado 24/7 para Zero en VPS (Ubuntu / Debian)
# Ejecuta: sudo bash despliegue_vps.sh [tu-dominio.com]
# ==============================================================================

set -e

DOMAIN="${1:-}"

echo "=================================================="
echo "  Iniciando instalación y despliegue de Zero 24/7"
echo "=================================================="

# 1. Actualizar sistema e instalar dependencias básicas
echo "--> [1/5] Actualizando paquetes del sistema..."
apt-get update -y
apt-get install -y python3 sqlite3 curl git tzdata debian-keyring debian-archive-keyring apt-transport-https

# Configurar zona horaria Santo Domingo
timedatectl set-timezone America/Santo_Domingo || true

# 2. Instalar Caddy (Servidor web con HTTPS automático)
echo "--> [2/5] Instalando Caddy Server para HTTPS automático..."
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update -y
apt-get install -y caddy

# 3. Preparar directorio de la aplicación
APP_DIR="/opt/zero"
echo "--> [3/5] Configurando aplicación en $APP_DIR..."
mkdir -p "$APP_DIR/data" "$APP_DIR/respaldos"

# Si el script se ejecuta dentro de la carpeta con el código, copiar los archivos
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$CURRENT_DIR/app.py" ] && [ "$CURRENT_DIR" != "$APP_DIR" ]; then
    cp -r "$CURRENT_DIR/"* "$APP_DIR/"
fi

chown -R www-data:www-data "$APP_DIR"
chmod -R 750 "$APP_DIR"

# 4. Configurar servicio systemd para ejecución continua 24/7
echo "--> [4/5] Configurando servicio del sistema (systemd)..."
cat <<EOF > /etc/systemd/system/zero.service
[Unit]
Description=Zero ERP & Business Suite
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/app.py --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Environment=TZ=America/Santo_Domingo

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable zero
systemctl restart zero

# 5. Configurar Caddy para acceso HTTP / HTTPS
echo "--> [5/5] Configurando proxy web..."
if [ -n "$DOMAIN" ]; then
cat <<EOF > /etc/caddy/Caddyfile
$DOMAIN {
    reverse_proxy 127.0.0.1:8000
}
EOF
else
cat <<EOF > /etc/caddy/Caddyfile
:80 {
    reverse_proxy 127.0.0.1:8000
}
EOF
fi

systemctl reload caddy || systemctl restart caddy

# 6. Configurar respaldo diario automático en cron
cat <<'EOF' > /opt/zero/auto_backup.sh
#!/bin/bash
BACKUP_DIR="/opt/zero/respaldos"
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M%S)
sqlite3 /opt/zero/data/zero.sqlite3 ".backup '$BACKUP_DIR/backup_$DATE.sqlite3'"
# Mantener solo los últimos 30 días de respaldo
find "$BACKUP_DIR" -name "backup_*.sqlite3" -mtime +30 -delete
EOF
chmod +x /opt/zero/auto_backup.sh

# Programar a las 3:00 AM diario
(crontab -l 2>/dev/null | grep -v "/opt/zero/auto_backup.sh" ; echo "0 3 * * * /opt/zero/auto_backup.sh") | crontab -

echo "=================================================="
echo "  ¡Despliegue completado con éxito!"
echo "=================================================="
if [ -n "$DOMAIN" ]; then
    echo "Su sistema está activo en: https://$DOMAIN"
else
    SERVER_IP=$(curl -s https://api.ipify.org || echo "IP_DEL_SERVIDOR")
    echo "Su sistema está activo en: http://$SERVER_IP"
fi
echo "Servicio activo en segundo plano 24/7 (systemd: zero.service)"
echo "Respaldos programados diarios en: /opt/zero/respaldos"
