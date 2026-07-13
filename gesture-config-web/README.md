# Gesture Shortcuts — config website

Small React + Express app for customizing the 1–4 finger shortcut gestures
used by `hand_mouse.py`'s **shortcuts mode** (press `g` there to toggle it).

No database — the Express server reads and writes a single JSON file,
`gestures_config.json`, and `hand_mouse.py` reads that *same file* directly
(auto-reloading it every ~2 seconds, or instantly if you press `r` in the
webcam window).

## Expected folder layout

```
C:\hackzen\
  hand_mouse.py
  gestures_config.json      <- created automatically on first save
  gesture-config-web\
    server\
    client\
```

The server's default `CONFIG_FILE_PATH` is two folders up from `server.js`,
which lands on `C:\hackzen\gestures_config.json` in this layout — right next
to `hand_mouse.py`. If your layout is different, copy
`server/.env.example` to `server/.env` and set `CONFIG_FILE_PATH` to the
absolute path of wherever `hand_mouse.py` lives.

## Run it

**Backend:**
```
cd gesture-config-web/server
npm install
npm start
```
Runs on http://localhost:5000.

**Frontend** (separate terminal):
```
cd gesture-config-web/client
npm install
npm run dev
```
Opens on http://localhost:5173 and proxies `/api` calls to the backend.

## Using it

1. Open http://localhost:5173.
2. For each of the four finger-count slots, pick an action type (open an app,
   open a website, run a keyboard shortcut, control media, or take a
   screenshot) and fill in the value.
3. Click **Save changes**.
4. In `hand_mouse.py`, press `g` to enter shortcuts mode, then hold up the
   matching number of fingers (index/middle/ring/pinky — thumb doesn't
   count) for about a second to fire the action.

## Action types

| Type | Value format | Example |
|---|---|---|
| `app` | one of `chrome`, `vscode`, `calculator`, `explorer`, `notepad` | `chrome` |
| `website` | a full URL | `https://github.com` |
| `shortcut` | keys joined with `+` | `ctrl+shift+esc` |
| `media` | one of `playpause`, `next`, `prev`, `volume_up`, `volume_down`, `mute` | `playpause` |
| `screenshot` | (no value needed) | — |
