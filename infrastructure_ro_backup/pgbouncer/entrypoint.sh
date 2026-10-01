#!/bin/sh
set -eu
: "${POSTGRES_DB:=localgram}"
: "${POSTGRES_USER:=localgram}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}"
printf '"%s" "%s"\n' "$POSTGRES_USER" "$POSTGRES_PASSWORD" > /etc/pgbouncer/userlist.txt
envsubst < /etc/pgbouncer/pgbouncer.ini.template > /etc/pgbouncer/pgbouncer.ini
exec pgbouncer /etc/pgbouncer/pgbouncer.ini
