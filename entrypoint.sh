#!/bin/sh
set -e

# Set default values if not provided
DATABASE_HOST=${DATABASE_HOST:-db}
DATABASE_PORT=${DATABASE_PORT:-5432}

echo "Waiting for Postgres at $DATABASE_HOST:$DATABASE_PORT..."
while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
  sleep 1
done
echo "Postgres is ready"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting application..."
exec "$@"