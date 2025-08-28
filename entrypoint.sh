#!/bin/sh
set -e

echo "Waiting for Postgres..."
until nc -z $DATABASE_HOST $DATABASE_PORT; do
  sleep 1
done
echo "Postgres is ready"

python manage.py migrate --noinput
exec "$@"
