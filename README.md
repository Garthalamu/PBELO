# PBELO — Pickleball ELO Tracker

A Django web app for pickleball organizers to record game results and track player ratings over time. ELO ratings are calculated separately for singles and doubles, with a margin-of-victory multiplier that rewards dominant wins.

## Features

- **Leaderboard** — Live singles and doubles rankings with ELO countup animation and podium highlighting (gold/silver/bronze)
- **Player profiles** — Per-player stat pages showing ELO history charts, W/L records, streaks, peak ELO, and head-to-head breakdowns
- **Match history** — Full game timeline filterable by singles or doubles
- **Awards system** — Players earn visual awards based on standing and performance:
  - 🥇 🥈 🥉 Podium awards for the top 3 ranked players (singles or doubles)
  - 🧪 Best Chemistry for the doubles pair with the highest win rate (min. 5 games together)
  - 🔥 Hot Streak for players on an active win streak of 3 or more
- **Confetti** — Award-colored confetti fires on hero name click for players holding any award
- **Best Teammate** — Win-rate-based best doubles partner (min. 5 games together)
- **Nemesis** — The opponent a player has lost to the most

## ELO Model

- K-factor: 24
- Margin-of-victory multiplier: `log2(|score_diff| + 1)` applied symmetrically
- Singles: standard two-player update
- Doubles: team rating = average of both players' ELO; each teammate receives the same delta

## Setup

```bash
uv sync                              # install dependencies
uv run python manage.py migrate      # apply migrations
uv run python manage.py runserver    # start dev server at http://127.0.0.1:8000
```

```bash
uv run python manage.py createsuperuser   # create admin user
```

ELO ratings can be fully recalculated from game history via the Django admin panel.

## Tech Stack

- **Backend** — Django 6, SQLite
- **Frontend** — Custom dark-theme CSS, Bootstrap Icons, Plotly.js (ELO history charts)
- **Auth** — Password-gate middleware with optional environment-variable hashing
