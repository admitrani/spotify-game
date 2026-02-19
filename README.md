# Spotify Guessing Game

A Python CLI game that turns your own Spotify saved tracks into a timed identification challenge.

## Project Scope

This project is intentionally scoped as a local, single-player command-line game.

What it does:
- Authenticates a user with Spotify OAuth.
- Syncs and caches the user’s saved tracks.
- Plays short randomized snippets on an active Spotify device.
- Presents multiple-choice answers and scores the run.
- Persists run summaries for high score and history.

What it does not do:
- Multi-user sessions, matchmaking, or leaderboards.
- Web UI or mobile UI.
- Cloud backend or account storage outside local files.

## Game Logic (Technical Overview)

Each run is a loop of independent rounds.

1. Candidate selection:
- Pick one track from the cached library as the correct answer.
- Sample three distinct distractors from the same library.
- Shuffle the 4 options.

2. Round render:
- Draw scoreboard + countdown + wrapped option list in terminal.
- Show one-line prompt for immediate numeric input (`1-4`) or quit (`q`).

3. Playback + input race:
- Start playback of the selected track at a random valid position.
- Run a timed input loop that updates remaining time while listening for keys.
- Resolve round status as one of: `answered`, `timeout`, `quit`, or `invalid`.

4. Evaluation:
- If the selected option URI matches the round track URI, increment score.
- On wrong answer / timeout / quit, end the run and print outcome.

5. Persistence:
- Append a JSON summary row to `game_history.jsonl`.
- Recompute high score from history and display it.

## Architecture

```text
main.py
  -> spotify_game/cli.py                 # startup orchestration
      -> spotify_game/env.py             # .env loading + cache migration
      -> spotify_game/spotify_client.py  # OAuth + Spotipy client lifecycle
      -> spotify_game/library.py         # Spotify saved-track sync/cache
      -> spotify_game/game.py            # core round loop + scoring
          -> spotify_game/playback.py    # device selection + playback control
          -> spotify_game/ui.py          # terminal rendering + timed input
      -> spotify_game/history.py         # run history + high score
```

## Use This With Your Own Spotify Account

### 1. Prerequisites

- Python 3.10+
- A Spotify account with playback control available on at least one device
- Spotify Premium (required by Spotify for the playback-control endpoints used here)
- A Spotify app in the Spotify Developer Dashboard

### 2. Create Spotify app credentials

1. Open the Spotify Developer Dashboard and create an app.
2. Copy your app’s `Client ID` and `Client Secret`.
3. Add a Redirect URI in app settings (must exactly match your `.env`).

A common local callback URI is:
- `https://127.0.0.1:8888/callback`

### 3. Configure environment

```bash
cp .env.example .env
```

Set values in `.env`:

```bash
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=https://127.0.0.1:8888/callback
```

### 4. Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py --refresh-library
```

The first run opens a browser for OAuth consent and builds `library_data.json` from your saved tracks.

After initial sync, normal runs are fast:

```bash
python3 main.py
```

## CLI Options

```bash
# Force full saved-track resync from Spotify API
python3 main.py --refresh-library

# Configure round snippet duration
python3 main.py --snippet-seconds 15

# Optional round limit (0 = unlimited)
python3 main.py --max-rounds 10
```

## Controls

During a round:
- Press `1`, `2`, `3`, or `4` to answer.
- Press `q` to quit.

After game over:
- Press `1` to play again.
- Press `2` to exit.

## Local Data Files

- `.spotifycache`: OAuth token cache.
- `library_data.json`: normalized saved-track library cache.
- `game_history.jsonl`: one JSON object per completed run.

## Troubleshooting

- `No available Spotify devices`:
  Open Spotify on phone/desktop/web player and make sure it is active.
- Redirect URI/auth errors:
  Verify `.env` redirect URI matches the Developer Dashboard exactly.
- Empty or stale library:
  Run once with `--refresh-library`.
