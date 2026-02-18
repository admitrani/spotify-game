# Spotify Guessing Game

A modular Python CLI game that uses your Spotify saved tracks for timed song-guess rounds.

## Features

- OAuth login with token cache (`.spotifycache`)
- Full saved-library sync with Spotify pagination (50/page, no 50-track cap)
- Local library cache (`library_data.json`) for fast startup
- 15-second timed guessing rounds by default
- Snippet start position is guaranteed to allow a full snippet (never starts in the final snippet window)
- Clean terminal UI with full wrapped track/artist names
- Live countdown timer and immediate game-over on timeout
- Fast answer input: press `1-4` directly (no Enter needed in interactive terminals)
- Playback pause on game end to avoid songs continuing in Spotify
- Replay flow after each game with a simple selector (`[1] Yes / [2] No`)
- Run logging to `game_history.jsonl` for analytics and reproducibility

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create env file:

```bash
cp .env.example .env
```

4. Fill `.env`:

```bash
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=https://127.0.0.1:8888/callback
```

5. In Spotify Developer Dashboard, add the same redirect URI from `.env`.

## Run

```bash
python3 main.py
```

Equivalent module entrypoint:

```bash
python3 -m spotify_game
```

## CLI Options

```bash
# Re-sync saved tracks from Spotify
python3 main.py --refresh-library

# Snippet length in seconds
python3 main.py --snippet-seconds 15

# Optional round cap (0 = unlimited)
python3 main.py --max-rounds 10
```

## Controls

- During a round:
  - Press `1`, `2`, `3`, or `4` to answer
  - Press `q` to quit
- After game over:
  - Press `1` to play again
  - Press `2` to exit

## Project Structure

```text
spotify_game/
  __main__.py        # module entrypoint
  cli.py             # arg parsing + app orchestration
  config.py          # constants and file paths
  env.py             # .env loading and token cache migration
  spotify_client.py  # Spotipy auth client/session lifecycle
  library.py         # track normalization + cache/sync logic
  playback.py        # device resolution + snippet playback/pause
  ui.py              # terminal rendering + timed input
  game.py            # core game loop
  history.py         # JSONL run logging
main.py              # thin launcher for python3 main.py
```

## Output Files

- `library_data.json`: normalized local track cache
- `game_history.jsonl`: one JSON object per game run
