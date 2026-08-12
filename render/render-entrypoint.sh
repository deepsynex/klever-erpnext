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

echo "Fixing ownership of mounted sites volume..."
chown -R frappe:frappe sites

echo "Linking baked assets into the sites volume..."
rm -rf sites/assets
ln -sf /home/frappe/frappe-bench/assets sites/assets
chown -h frappe:frappe sites/assets

echo "Waiting for MariaDB at ${DB_HOST}:${DB_PORT}..."
wait-for-it -t 120 "${DB_HOST}:${DB_PORT}"

if [ ! -f sites/apps.txt ]; then
  ls -1 apps > sites/apps.txt
  chown frappe:frappe sites/apps.txt
fi

export DB_HOST DB_PORT DB_ROOT_PASSWORD REDIS_CACHE REDIS_QUEUE SITE_NAME ADMIN_PASSWORD

cat > /tmp/bench-setup.sh <<'SETUP'
#!/bin/bash
set -e
cd /home/frappe/frappe-bench

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
SETUP
chmod 755 /tmp/bench-setup.sh

su frappe -c /tmp/bench-setup.sh

exec "$@"
