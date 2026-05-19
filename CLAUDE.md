# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pickleball ELO Tracker — a Django web app for organizers to record pickleball game results and compute ELO ratings. ELO is calculated separately for singles and doubles, with modifications to improve accuracy for this sport.

## Setup & Commands

```
uv sync                          # install dependencies
uv run python manage.py migrate  # apply migrations
uv run python manage.py runserver  # start dev server (http://127.0.0.1:8000)
```

```
uv run python manage.py makemigrations  # create migrations after model changes
uv run python manage.py createsuperuser  # create admin user
```

## Testing

```
uv run python manage.py test              # run all tests
uv run python manage.py test tracker      # run tests for one app
uv run python manage.py test tracker.tests.TestClassName.test_method  # single test
```

## Architecture

Django 6 + SQLite. Bootstrap 5 loaded via CDN (no extra package).

**Project config**: `pbelo/` — settings, root urls, wsgi/asgi.

**`tracker/`** — the main app. All pickleball domain logic lives here: models (Player, Game, etc.), views, urls, and forms.

**`templates/`** — project-level templates.
- `base.html` — Bootstrap 5 CDN, navbar, message alerts. All other templates extend this.
- `tracker/` — app-specific templates that extend `base.html`.

Template blocks in `base.html`: `title`, `extra_css`, `content`, `extra_js`.
