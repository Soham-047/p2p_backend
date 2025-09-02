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

# Skip local Redis wait if using external
if [ -z "$EXTERNAL_REDIS" ]; then
  echo "Waiting for Redis at $REDIS_HOST:$REDIS_PORT..."
  while ! nc -z $REDIS_HOST $REDIS_PORT; do
    sleep 1
  done
  echo "Redis is ready"
else
  echo "Skipping Redis wait (using external Redis)"
fi

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting application..."
exec "$@"
