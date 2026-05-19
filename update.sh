#!/bin/bash
set -e

echo ">> Pulling latest code..."
git pull

echo ">> Installing dependencies..."
uv sync

echo ">> Running migrations..."
uv run python manage.py migrate

echo ">> Collecting static files..."
uv run python manage.py collectstatic --noinput

echo ">> Reloading web app..."
touch /var/www/cgartner37_pythonanywhere_com_wsgi.py

echo "Done! Site is live."
