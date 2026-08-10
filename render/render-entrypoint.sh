#!/bin/bash
set -e

: "${DB_HOST:?DB_HOST is required}"
: "${DB_PORT:=3306}"
: "${DB_ROOT_PASSWORD:?DB_ROOT_PASSWORD is required}"
: "${REDIS_CACHE:?REDIS_CACHE is required}"
: "${REDIS_QUEUE:?REDIS_QUEUE is required}"
: "${SITE_NAME:?SITE_NAME is required}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD is required}"

cd /home/frappe/frappe-bench

echo "Linking baked assets into the sites volume..."
rm -rf sites/assets
ln -sf /home/frappe/frappe-bench/assets sites/assets

echo "Waiting for MariaDB at ${DB_HOST}:${DB_PORT}..."
wait-for-it -t 120 "${DB_HOST}:${DB_PORT}"

if [ ! -f sites/apps.txt ]; then
  ls -1 apps > sites/apps.txt
fi

bench set-config -g db_host "$DB_HOST"
bench set-config -gp db_port "$DB_PORT"
bench set-config -g redis_cache "$REDIS_CACHE"
bench set-config -g redis_queue "$REDIS_QUEUE"
bench set-config -g redis_socketio "$REDIS_QUEUE"
bench set-config -gp socketio_port 9000

if [ ! -d "sites/${SITE_NAME}" ]; then
  echo "Site ${SITE_NAME} not found, creating it..."
  bench new-site "$SITE_NAME" \
    --mariadb-user-host-login-scope='%' \
    --db-root-password "$DB_ROOT_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --install-app erpnext \
    --set-default
else
  echo "Site ${SITE_NAME} already exists, running migrations..."
  bench --site "$SITE_NAME" migrate
fi

exec "$@"
