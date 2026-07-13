# AirPilot — Setup Steps

## Install

1. Download **Python 3.11.x (64-bit)**:
   https://www.python.org/downloads/release/python-3119/

2. During installation, check **"Add Python to PATH"**.

3. Verify the installation:

   ```bash
   python --version
   ```

   You should see:

   ```text
   Python 3.11.x
   ```

4. Create a virtual environment:

   ```bash
   python -m venv venv
   ```

5. Activate it:

   ```bash
   venv\Scripts\activate
   ```

6. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

7. If you do not have a `requirements.txt` file, install them manually:

   ```bash
   pip install opencv-python mediapipe==0.10.14 pyautogui numpy
   ```

---

## Run

```bash
python temp.py
```

1. Allow camera access if Windows asks.
2. Point your index finger at the top-left of your control area and press **Space**.
3. Do the same for the bottom-right.
4. Move your hand — the cursor follows your index finger.

---

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

---

## Keys

```
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
x : calibrate the cm-measurement scale (hold both middle fingertips a known distance apart, press SPACE in the webcam window, then type the real distance in cm)
f : toggle fullscreen for the webcam window (starts in fullscreen by default)
r : force-reload gestures_config.json immediately
[ : make edges harder to reach (shrink reach margin)
] : make edges easier to reach (grow reach margin, less physical stretch needed)
```

---

## Website


If you see **"Couldn't reach the config server"**, it means the backend is not running. Check the backend terminal for any error messages and start it again.

Lastly, open **`start_website.bat`**. This automatically opens the website.

Open:

```
http://localhost:5173
```

Keep shortcuts on your own.
