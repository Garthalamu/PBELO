# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pickleball ELO Tracker — a Django web app for organizers to record pickleball game results and compute ELO ratings. ELO is calculated separately for singles and doubles with a margin-of-victory multiplier.

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

Django 6 + SQLite. Bootstrap 5 loaded via CDN. Plotly.js (v2.35.2) via CDN for charts; `plotly` Python package generates chart JSON server-side.

**Project config**: `pbelo/` — settings, root urls, wsgi/asgi.

**`tracker/`** — the main app. All pickleball domain logic lives here.

**`templates/`** — project-level templates.
- `base.html` — Bootstrap 5 CDN, navbar (Home / Matches / Record Game), message alerts.
- `tracker/` — app-specific templates that extend `base.html`.

Template blocks in `base.html`: `title`, `extra_css`, `content`, `extra_js`.

## Models (`tracker/models.py`)

- **`Player`** — name (unique), `singles_elo` (default 1000), `doubles_elo` (default 1000), `created_at`
- **`Location`** — name (unique); required on every game (PROTECT delete)
- **`Game`** — `game_type` (singles/doubles), `played_at`, `location` FK, `team1_players`/`team2_players` M2M to Player, `team1_score`/`team2_score`; `winning_team` property returns 1, 2, or None
- **`EloChange`** — FK to Player + Game, `elo_before`, `elo_after`; `delta` property

## ELO Logic (`tracker/elo.py`)

- K = 24
- MOV multiplier: `log2(|score_diff| + 1)` applied to both sides (zero-sum preserved)
- Singles: standard two-player ELO
- Doubles: team rating = average of two players' `doubles_elo`; each player on a team gets the same delta
- `process_game(game)` dispatches to `process_singles` or `process_doubles` and bulk-creates `EloChange` records

## Views (`tracker/views.py`)

- **`home`** — leaderboard; prefetches all EloChanges, computes win counts in Python, returns `singles_board` / `doubles_board` sorted by ELO (only players with games)
- **`matches`** — all games split into `singles` / `doubles` context lists, ordered newest-first
- **`record_game`** — form POST creates Game + sets M2M players + calls `process_game()`
- **`player_detail`** — W/L stats, game rows, best teammate (Counter of doubles wins by partner), nemesis (Counter of losses by opponent across all types), ELO history charts, leaderboard rank for singles and doubles (`singles_rank` / `doubles_rank`)
- **`_build_elo_chart`** — returns Plotly figure JSON (closing ELO per day, line+markers, dotted 1000 baseline)

## Services (`tracker/services.py`)

- **`recalculate_all_elos()`** — resets all players to 1000, deletes all EloChanges, replays games in `played_at` order inside a transaction. Called from the Django admin. Does NOT use prefetch (so each game reads fresh ELOs from DB).

## Forms (`tracker/forms.py`)

`RecordGameForm` — validates: doubles requires player2 fields, no duplicate players across teams, no tied scores.

## Admin (`tracker/admin.py`)

`GameAdmin` has a custom "Recalculate ELO Ratings" button via `get_urls()` that hits `recalculate_all_elos()`. Confirm page at `templates/admin/tracker/game/recalculate_confirm.html`.

## Template Tags (`tracker/templatetags/leaderboard_tags.py`)

`subtract` filter — used in leaderboard/player templates to compute losses from `games_count - wins`.

## URL Structure

| URL | View | Name |
|-----|------|------|
| `/` | home | `home` |
| `/matches/` | matches | `matches` |
| `/record/` | record_game | `record_game` |
| `/players/<id>/` | player_detail | `player_detail` |
