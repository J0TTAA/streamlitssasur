# Guía de Despliegue — DocRef Dashboard

Instrucciones paso a paso para desplegar en una VM Linux con Docker y nginx.

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Preparar la VM](#2-preparar-la-vm)
3. [Clonar y configurar](#3-clonar-y-configurar)
4. [Primer despliegue](#4-primer-despliegue)
5. [Actualizar el sistema](#5-actualizar-el-sistema)
6. [Agregar o actualizar datos](#6-agregar-o-actualizar-datos)
7. [Configurar HTTPS / SSL](#7-configurar-https--ssl)
8. [Monitoreo y logs](#8-monitoreo-y-logs)
9. [Backups de la base de datos](#9-backups-de-la-base-de-datos)
10. [Resolver problemas comunes](#10-resolver-problemas-comunes)
11. [Referencia rápida de comandos](#11-referencia-rápida-de-comandos)

---

## 1. Requisitos previos

### En la VM

| Requisito | Versión mínima | Verificar |
|-----------|----------------|-----------|
| Linux | Ubuntu 22.04 / Debian 12 / RHEL 9 | `uname -r` |
| Docker Engine | 24.x | `docker --version` |
| Docker Compose plugin | 2.x | `docker compose version` |
| Git | 2.x | `git --version` |
| Puerto 80 abierto | — | regla de firewall / Security Group |
| Puerto 443 abierto (SSL) | — | solo si usas HTTPS |

### Red / firewall

```bash
# Ubuntu / Debian (ufw)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp   # solo para SSL
sudo ufw allow 22/tcp    # SSH (si no está ya)
sudo ufw reload

# RHEL / CentOS (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# AWS / GCP / Azure: abrir puertos en el Security Group / VPC Firewall
```

---

## 2. Preparar la VM

### Instalar Docker (Ubuntu/Debian)

```bash
# Actualizar paquetes
sudo apt-get update && sudo apt-get upgrade -y

# Instalar dependencias
sudo apt-get install -y ca-certificates curl gnupg

# Agregar repositorio oficial de Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
   https://download.docker.com/linux/ubuntu \
   $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker Engine + Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

# Permitir ejecutar Docker sin sudo (cerrar sesión y volver a entrar)
sudo usermod -aG docker $USER
```

### Instalar Docker (RHEL/CentOS)

```bash
sudo dnf install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### Verificar instalación

```bash
docker --version        # Docker version 27.x.x
docker compose version  # Docker Compose version v2.x.x
```

---

## 3. Clonar y configurar

```bash
# 1. Clonar el repositorio
cd /opt
sudo git clone https://github.com/<tu-usuario>/<tu-repo>.git docref
sudo chown -R $USER:$USER docref
cd docref

# 2. Crear el archivo de configuración
cp .env.example .env
nano .env          # editar contraseñas y parámetros
```

### Contenido de `.env`

```ini
# ── Contraseñas de la base de datos ──────────────────────────────────────────
POSTGRES_USER=interconsultas
POSTGRES_PASSWORD=ContraseñaSegura2024!   # <-- CAMBIAR
POSTGRES_DB=interconsultas

# ── Puertos (en producción dejar en 127.0.0.1) ───────────────────────────────
API_BIND=127.0.0.1       # la API solo es accesible desde nginx
FRONTEND_BIND=127.0.0.1  # el frontend solo es accesible desde nginx
```

> **Seguridad:** `API_BIND=127.0.0.1` y `FRONTEND_BIND=127.0.0.1` hacen que los  
> servicios internos no sean accesibles directamente desde internet — todo el  
> tráfico pasa por nginx.

---

## 4. Primer despliegue

### 4.1 Copiar los archivos de datos

```bash
# Copiar los JSON de interconsultas a la carpeta data/
cp /ruta/a/tus/datos/*.json /opt/docref/data/

# Verificar que están ahí
ls /opt/docref/data/
```

### 4.2 Ejecutar el script de despliegue

```bash
cd /opt/docref
bash deploy.sh
```

El script:
1. Verifica que Docker esté instalado
2. Revisa que `.env` exista (lo crea desde `.env.example` si no)
3. Construye las imágenes Docker
4. Levanta todos los servicios
5. Espera a que la API responda en `/health`
6. Verifica que nginx esté respondiendo en el puerto 80

### 4.3 Verificar el despliegue

```bash
# Estado de contenedores
docker compose ps

# Debe mostrar algo así:
# NAME                      STATUS          PORTS
# interconsultas_db         Up (healthy)    5432/tcp
# interconsultas_api        Up (healthy)    127.0.0.1:8000->8000/tcp
# interconsultas_frontend   Up              127.0.0.1:8501->8501/tcp
# interconsultas_nginx      Up              0.0.0.0:80->80/tcp

# Probar acceso
curl -s http://localhost/health   # debe responder: {"status":"ok"}
curl -I http://localhost/         # debe responder: HTTP/1.1 200 OK
```

Abrir en el navegador: **`http://IP_DE_LA_VM`**

---

## 5. Actualizar el sistema

Cuando hay cambios nuevos en el repositorio:

```bash
cd /opt/docref

# Opción A: usar el script (hace pull + rebuild automáticamente)
bash deploy.sh update

# Opción B: manual
git pull --ff-only
docker compose up --build -d
```

> Si los cambios son solo en el frontend (sin tocar la API), puedes reconstruir solo ese servicio:
> ```bash
> docker compose up --build -d frontend
> ```

---

## 6. Agregar o actualizar datos

La API siembra la base de datos **una sola vez** al arrancar (cuando `interconsultas` está vacía). Para agregar nuevas fuentes de datos:

### Agregar datos sin reiniciar la DB (primera vez)

```bash
# Copiar nuevos archivos mientras los contenedores están corriendo
cp nuevos_datos.json /opt/docref/data/

# La API los detectará en el próximo arranque
# Reiniciar solo la API para forzar re-seed (SOLO si la DB está vacía)
docker compose restart api
```

### Re-sembrar la base de datos desde cero

> ⚠️ **Esto borra TODAS las validaciones guardadas.**

```bash
cd /opt/docref

# Copiar los nuevos archivos JSON
cp /ruta/nuevos/*.json data/

# Bajar, borrar la base de datos y volver a subir
docker compose down -v
docker compose up -d
```

---

## 7. Configurar HTTPS / SSL

### 7.1 Con Let's Encrypt (Certbot) — recomendado

```bash
# Instalar certbot
sudo apt-get install -y certbot

# Obtener certificado (requiere dominio apuntando a la VM)
sudo certbot certonly --standalone \
    --preferred-challenges http \
    -d tu-dominio.cl \
    --email tu@email.cl \
    --agree-tos \
    --non-interactive

# Los certificados quedan en:
# /etc/letsencrypt/live/tu-dominio.cl/fullchain.pem
# /etc/letsencrypt/live/tu-dominio.cl/privkey.pem
```

### 7.2 Montar los certificados en Docker

En `docker-compose.yml`, la sección de nginx ya tiene el volumen preparado:

```yaml
nginx:
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - /etc/letsencrypt:/etc/nginx/certs:ro   # agregar esta línea
```

### 7.3 Actualizar `nginx/nginx.conf`

Descomentar y ajustar las secciones SSL del archivo:

```nginx
# Redirigir HTTP → HTTPS
server {
    listen 80;
    server_name tu-dominio.cl;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name tu-dominio.cl;

    ssl_certificate     /etc/nginx/certs/live/tu-dominio.cl/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/live/tu-dominio.cl/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # ... resto de la configuración (location /, /api/, etc.)
}
```

### 7.4 Habilitar el puerto 443 en docker-compose.yml

```yaml
nginx:
  ports:
    - "80:80"
    - "443:443"   # descomentar esta línea
```

### 7.5 Renovación automática de certificados

```bash
# Probar renovación (sin modificar nada)
sudo certbot renew --dry-run

# Agregar cron para renovación automática (cada día a las 2am)
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/bin/certbot renew --quiet && docker compose -f /opt/docref/docker-compose.yml restart nginx") | crontab -
```

---

## 8. Monitoreo y logs

### Ver logs en tiempo real

```bash
cd /opt/docref

# Todos los servicios
docker compose logs -f

# Solo un servicio
docker compose logs -f api
docker compose logs -f frontend
docker compose logs -f nginx
docker compose logs -f db
```

### Ver las últimas N líneas

```bash
docker compose logs --tail=100 api
```

### Verificar estado de salud

```bash
# Estado general
docker compose ps

# Health check manual
curl -s http://localhost/health

# Estadísticas de recursos
docker stats
```

### Configurar logrotate (logs del sistema)

```bash
# Crear archivo de configuración
sudo tee /etc/logrotate.d/docker-docref << 'EOF'
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    missingok
    delaycompress
    copytruncate
}
EOF
```

---

## 9. Backups de la base de datos

### Backup manual

```bash
cd /opt/docref

# Crear directorio de backups
mkdir -p backups

# Volcar la base de datos completa
docker compose exec db pg_dump \
    -U interconsultas \
    -d interconsultas \
    --no-owner \
    --no-acl \
    -F c \
    -f /tmp/backup.dump

# Copiar al host
docker cp interconsultas_db:/tmp/backup.dump \
    backups/interconsultas_$(date +%Y%m%d_%H%M%S).dump

echo "Backup creado en backups/"
ls -lh backups/
```

### Backup automático (cron diario)

```bash
# Crear script de backup
sudo tee /opt/docref/backup.sh << 'EOF'
#!/bin/bash
set -e
BACKUP_DIR=/opt/docref/backups
mkdir -p "$BACKUP_DIR"

FILENAME="interconsultas_$(date +%Y%m%d_%H%M%S).dump"

docker compose -f /opt/docref/docker-compose.yml exec -T db \
    pg_dump -U interconsultas -d interconsultas --no-owner --no-acl -F c \
    > "$BACKUP_DIR/$FILENAME"

# Mantener solo los últimos 30 backups
ls -t "$BACKUP_DIR"/*.dump | tail -n +31 | xargs -r rm --

echo "Backup: $BACKUP_DIR/$FILENAME ($(du -sh "$BACKUP_DIR/$FILENAME" | cut -f1))"
EOF

chmod +x /opt/docref/backup.sh

# Agregar al cron (todos los días a las 3am)
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/docref/backup.sh >> /opt/docref/backups/backup.log 2>&1") | crontab -
```

### Restaurar desde backup

```bash
cd /opt/docref

# Parar el frontend y la API (la DB sigue corriendo)
docker compose stop frontend api

# Restaurar
docker compose exec -T db pg_restore \
    -U interconsultas \
    -d interconsultas \
    --clean \
    --if-exists \
    < backups/interconsultas_20240101_030000.dump

# Reiniciar
docker compose start api frontend

echo "Restauración completada"
```

---

## 10. Resolver problemas comunes

### La aplicación no carga (timeout en el navegador)

```bash
# Verificar que nginx esté corriendo
docker compose ps nginx

# Ver errores de nginx
docker compose logs nginx

# Verificar que el puerto 80 esté abierto
sudo ss -tlnp | grep :80
```

### La API no arranca (error de conexión a DB)

```bash
# Ver logs de la API
docker compose logs api

# Verificar que la DB esté healthy
docker compose ps db

# Si la DB no está lista, reiniciar la API
docker compose restart api
```

### Los datos no aparecen en el frontend

```bash
# Verificar que los JSON estén en data/
ls -la /opt/docref/data/

# Verificar que la API los leyó (logs de seed)
docker compose logs api | grep "\[seed\]"

# Si no hay logs de seed, la DB ya tenía datos → re-seed
# (CUIDADO: borra validaciones)
docker compose down -v && docker compose up -d
```

### El frontend muestra "No se puede conectar a la API"

```bash
# Verificar que api esté healthy
docker compose ps api

# Probar la API directamente
curl http://localhost:8000/health

# Ver logs del frontend
docker compose logs frontend
```

### Error "no space left on device"

```bash
# Ver espacio en disco
df -h

# Limpiar imágenes y contenedores no usados
docker system prune -a

# Ver cuánto usan los volúmenes
docker system df
```

### Un contenedor se reinicia en bucle (crash loop)

```bash
# Ver por qué falló el último inicio
docker compose logs --tail=50 <servicio>

# Ver eventos del contenedor
docker inspect interconsultas_api | grep -A5 '"State"'
```

---

## 11. Referencia rápida de comandos

```bash
# ── Operaciones básicas ───────────────────────────────────────────────────────
bash deploy.sh              # primer despliegue
bash deploy.sh update       # actualizar desde git

docker compose up -d        # levantar (sin reconstruir)
docker compose up --build -d # levantar y reconstruir imágenes
docker compose down         # apagar (conserva datos)
docker compose down -v      # apagar y BORRAR base de datos
docker compose restart      # reiniciar todos los servicios
docker compose restart api  # reiniciar solo la API

# ── Estado y logs ─────────────────────────────────────────────────────────────
docker compose ps           # estado de contenedores
docker compose logs -f      # logs en tiempo real (todos)
docker compose logs -f api  # logs de la API
docker stats                # uso de CPU/memoria en tiempo real

# ── Base de datos ─────────────────────────────────────────────────────────────
# Conectarse a la DB
docker compose exec db psql -U interconsultas -d interconsultas

# Queries útiles dentro de psql:
# \dt                                    -- listar tablas
# SELECT fuente, COUNT(*) FROM interconsultas GROUP BY fuente;
# SELECT COUNT(*) FROM interconsultas WHERE validado IS NOT NULL;
# SELECT COUNT(*) FROM claims;           -- claims activos

# Backup manual
bash /opt/docref/backup.sh

# ── Nginx ─────────────────────────────────────────────────────────────────────
docker compose exec nginx nginx -t        # verificar configuración
docker compose restart nginx              # recargar nginx

# ── Actualización ─────────────────────────────────────────────────────────────
git pull && docker compose up --build -d  # actualizar y reconstruir todo
docker compose up --build -d frontend    # reconstruir solo el frontend
docker compose up --build -d api         # reconstruir solo la API
```
