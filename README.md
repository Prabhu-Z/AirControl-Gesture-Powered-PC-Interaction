# AirPilot — Setup Steps

## Install

1. Install Python from https://www.python.org/downloads/ — tick **"Add Python to PATH"** during install.
2. Open the AirPilot folder, click the address bar, type `powershell`, press Enter.
3. Create a virtual environment:
   ```
   python -m venv venv
   ```
4. Activate it:
   ```
   venv\Scripts\activate
   ```
5. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
6.If you do not have a requirements file, install them manually.

```
  pip install opencv-python mediapipe pyautogui numpy

## Run

```
python temp.py
```

6. Allow camera access if Windows asks.
7. Point your index finger at the top-left of your control area, press **Space**. Do the same for bottom-right.
8. Move your hand — the cursor follows your index finger.

## Gestures

| Gesture | Action |
|---|---|
| Index finger | Move cursor |
| Pinch thumb + index (quick) | Left click |
| Pinch thumb + index (hold + move) | Drag |
| Pinch thumb + middle | Right click |
| Index + middle up, move hand | Scroll |
| Thumb + pinky, change distance | Volume |
| Both hands, index out, move apart | Zoom |
| Both hands, only middle out, move apart | Measure |
| Open palm | Freeze cursor |
| Closed fist (hold) | Screenshot |

## Keys

q : quit
c : re-run mouse-control calibration
m : toggle mirrored / left-handed control mode
d : toggle dwell-click mode (hover to click, accessibility mode)
h : toggle HUD overlay (also shows live per-finger extended/curled debug readout)
v : toggle voice commands (only if SpeechRecognition + pyaudio installed)
g : toggle app-SHORTCUTS mode (hold up 1-4 fingers to launch the mapped action)
p : toggle PRESENTATION mode (swipe hand left/right to change slides)
w : toggle WRITE/DRAW mode (air-writing with your index finger)
e : erase/clear the write-mode drawing canvas
s : save the current write-mode drawing to a PNG
x : calibrate the cm-measurement scale (hold both middle fingertips a known distance
    apart, press SPACE in the webcam window, then type the real distance in cm)
f : toggle fullscreen for the webcam window (starts in fullscreen by default)
r : force-reload gestures_config.json immediately
[ : make edges harder to reach (shrink reach margin)
] : make edges easier to reach (grow reach margin, less physical stretch needed)


## Website:
1. Keep two terminal windows open.

Terminal 1: Run the backend (port 5000)
Terminal 2: Run the frontend (port 5173)

Do not close either terminal. If you close one, the app will stop working.

If you see "Couldn't reach the config server", it means the backend is not running. Check the backend terminal for any error messages and start it again.
```
lastly open the start_website.bat file this automatiically opens the website
```
Open http://localhost:5173
and keep shortcuts on your own
