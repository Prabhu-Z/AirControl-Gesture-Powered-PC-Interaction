"""
Hand Gesture Mouse Controller
==============================

Controls the OS mouse cursor with your webcam + one hand.

Core gestures
-------------
- Move cursor   : point with index finger inside the calibrated box
- Left click    : quick thumb + index pinch
- Drag          : hold thumb + index pinch and move
- Right click   : thumb + middle finger pinch
- Scroll        : hold up index + middle finger (others curled), move hand up/down
- Volume        : thumb + pinky extended, index + middle curled (others curled), change
                  distance between thumb and pinky. Ring finger is ignored on purpose --
                  most people physically can't curl the ring finger while extending the
                  pinky, so requiring it "curled" made this gesture unreliable before.
- Zoom          : show BOTH hands, index fingers extended, move index fingertips apart / together
- Measure (cm)  : show BOTH hands, ONLY middle fingers extended (index down) -> live distance
                  between the two middle fingertips, shown in cm once calibrated (see 'x' below)
- Write / draw  : toggle with 'w'. Point with index finger to draw; pinch thumb+index to lift
                  the pen. Ink persists on screen until cleared.
- Tab switch    : hold up 4 fingers (index+middle+ring+pinky, thumb tucked in) and swipe your
                  hand LEFT -> RIGHT for next tab (Ctrl+Tab), RIGHT -> LEFT for previous tab
                  (Ctrl+Shift+Tab). Only active while shortcuts-mode ('g') is OFF, so it never
                  collides with your 1-4 finger app-shortcuts.
- Minimize      : same 4-finger pose, swipe your hand TOP -> BOTTOM to minimize the active
                  window. Also only active while shortcuts-mode is OFF.
- Freeze        : open palm (all 5 fingers extended) -> cursor locks, no accidental input
- Screenshot    : closed fist (all 5 fingers curled), held briefly

Mode toggles (keys, webcam window must be focused)
---------------------------------------------------
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

Notes on accuracy
------------------
Finger "extended/curled" state is computed from the mcp-pip-tip joint angle for the
four fingers (index/middle/ring/pinky), which stays reliable regardless of hand
rotation/tilt. The thumb uses a separate palm-relative check (how far the thumb tip
has splayed away from the pinky-MCP line vs. the thumb's own base), since the thumb's
joint geometry doesn't work with the same straight-line test. The 1-4 finger shortcut
count is also smoothed over a few recent frames so a single noisy reading can't reset
your hold timer.

Custom gesture configuration
-----------------------------
Shortcut-mode actions (1-4 fingers) are loaded from gestures_config.json, next
to this script. That file is meant to be edited by the companion React/Node
web app (see gesture-config-web/) -- point its backend's CONFIG_FILE_PATH at
this same file and this script will pick up changes automatically (checked
every ~2s), or press 'r' to reload immediately.

If the file is missing, sensible defaults are used (Chrome / VS Code /
Calculator / File Explorer).

Optional extras
----------------
System volume control needs (Windows only):
    pip install pycaw comtypes
Voice commands need:
    pip install SpeechRecognition pyaudio
The script runs fine without either -- those features just no-op.
"""

import json
import math
import os
import platform
import subprocess
import time
import webbrowser
from collections import deque
from datetime import datetime

import cv2
import mediapipe as mp
import numpy as np
import pyautogui

# ---------------------------------------------------------------- optional: system volume
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    _devices = AudioUtilities.GetSpeakers()
    _interface = _devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume_ctrl = cast(_interface, POINTER(IAudioEndpointVolume))
    VOLUME_AVAILABLE = True
except Exception:
    volume_ctrl = None
    VOLUME_AVAILABLE = False

# ---------------------------------------------------------------- optional: voice commands
try:
    import threading
    import speech_recognition as sr

    VOICE_LIB_AVAILABLE = True
except Exception:
    VOICE_LIB_AVAILABLE = False

voice_enabled = False
voice_commands = deque(maxlen=5)


def _voice_listener():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
    while voice_enabled:
        try:
            with mic as source:
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=3)
            text = recognizer.recognize_google(audio).lower()
            voice_commands.append(text)
        except Exception:
            continue


# ---------------------------------------------------------------- gesture config (shared with web app)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gestures_config.json")

DEFAULT_CONFIG = {
    "1": {"type": "app", "value": "chrome", "label": "Chrome"},
    "2": {"type": "app", "value": "vscode", "label": "VS Code"},
    "3": {"type": "app", "value": "calculator", "label": "Calculator"},
    "4": {"type": "app", "value": "explorer", "label": "File Explorer"},
}

KNOWN_APPS = {
    "chrome": {
        "Windows": "start chrome",
        "Darwin": "open -a \"Google Chrome\"",
        "Linux": "google-chrome",
    },
    "vscode": {
        "Windows": "code",
        "Darwin": "open -a \"Visual Studio Code\"",
        "Linux": "code",
    },
    "calculator": {
        "Windows": "calc",
        "Darwin": "open -a Calculator",
        "Linux": "gnome-calculator",
    },
    "explorer": {
        "Windows": "explorer",
        "Darwin": "open .",
        "Linux": "xdg-open .",
    },
    "notepad": {
        "Windows": "notepad",
        "Darwin": "open -a TextEdit",
        "Linux": "gedit",
    },
}

MEDIA_KEYS = {
    "playpause": "playpause",
    "next": "nexttrack",
    "prev": "prevtrack",
    "volume_up": "volumeup",
    "volume_down": "volumedown",
    "mute": "volumemute",
}


def load_gesture_config():
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        # merge with defaults so missing slots still work
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception as e:
        print(f"[config] failed to read {CONFIG_PATH}: {e} -- using defaults")
        return dict(DEFAULT_CONFIG)


def launch_app(name):
    system = platform.system()
    entry = KNOWN_APPS.get(name)
    try:
        if entry and system in entry:
            subprocess.Popen(entry[system], shell=True)
        else:
            # not a known app name -- try it as a raw path/command
            if system == "Windows":
                os.startfile(name)
            else:
                subprocess.Popen([name])
    except Exception as e:
        print(f"[shortcut] couldn't launch '{name}': {e}")


def run_action(action):
    """Dispatch a gesture-config action dict: {type, value}."""
    if not action:
        return
    a_type = action.get("type")
    value = action.get("value", "")
    try:
        if a_type == "app":
            launch_app(value)
        elif a_type == "website":
            webbrowser.open(value)
        elif a_type == "shortcut":
            keys = [k.strip() for k in value.split("+") if k.strip()]
            if keys:
                pyautogui.hotkey(*keys)
        elif a_type == "media":
            key = MEDIA_KEYS.get(value)
            if key:
                pyautogui.press(key)
        elif a_type == "screenshot":
            take_screenshot()
    except Exception as e:
        print(f"[shortcut] action failed ({action}): {e}")


def take_screenshot():
    pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
    out_dir = pictures_dir if os.path.isdir(pictures_dir) else os.getcwd()
    fname = f"gesture_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(out_dir, fname)
    try:
        pyautogui.screenshot().save(path)
        print(f"[screenshot] saved to {path}")
    except Exception as e:
        print(f"[screenshot] failed: {e}")


def set_system_volume(level):
    """Best-effort cross-platform system volume control. level is 0.0-1.0.
    Windows uses pycaw (if installed). macOS/Linux shell out to the OS's own
    volume tool so the gesture actually does something even without pycaw --
    this is very likely why volume "wasn't adding" before: pycaw is Windows-only,
    so on Mac/Linux the old code silently did nothing.
    """
    system = platform.system()
    try:
        if system == "Windows":
            if VOLUME_AVAILABLE:
                volume_ctrl.SetMasterVolumeLevelScalar(level, None)
            else:
                print("[volume] pycaw not installed -- run: pip install pycaw comtypes")
        elif system == "Darwin":
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {int(level * 100)}"],
                check=False, capture_output=True,
            )
        else:  # Linux and anything else: try PulseAudio/PipeWire first, fall back to ALSA
            result = subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(level * 100)}%"],
                check=False, capture_output=True,
            )
            if result.returncode != 0:
                subprocess.run(
                    ["amixer", "-D", "pulse", "sset", "Master", f"{int(level * 100)}%"],
                    check=False, capture_output=True,
                )
    except FileNotFoundError:
        print(f"[volume] no volume control tool found for {system}")
    except Exception as e:
        print(f"[volume] failed to set system volume: {e}")


def minimize_active_window():
    """Best-effort cross-platform minimize of the currently focused window."""
    system = platform.system()
    try:
        if system == "Windows":
            pyautogui.hotkey('win', 'down')
        elif system == "Darwin":
            pyautogui.hotkey('command', 'm')
        else:
            pyautogui.hotkey('super', 'h')  # GNOME default; remap in DE settings if different
    except Exception as e:
        print(f"[nav] minimize failed: {e}")



    pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
    out_dir = pictures_dir if os.path.isdir(pictures_dir) else os.getcwd()
    fname = f"gesture_drawing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(out_dir, fname)
    try:
        cv2.imwrite(path, canvas)
        print(f"[write] drawing saved to {path}")
    except Exception as e:
        print(f"[write] failed to save: {e}")


# ---------------------------------------------------------------- One Euro Filter
class OneEuroFilter:
    """Adaptive low-pass filter: smooths slow drift, stays responsive on fast movement.
    This is what satisfies 'adaptive smoothing based on hand speed' -- beta scales the
    cutoff frequency by how fast the signal is currently moving.
    """

    def __init__(self, freq=30.0, mincutoff=1.0, beta=0.02, dcutoff=1.0):
        self.freq = freq
        self.mincutoff = mincutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    def _alpha(self, cutoff):
        te = 1.0 / self.freq
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / te)

    def filter(self, x, t=None):
        t = t if t is not None else time.time()
        if self.t_prev is not None:
            dt = t - self.t_prev
            if dt > 0:
                self.freq = 1.0 / dt
        self.t_prev = t

        if self.x_prev is None:
            self.x_prev = x
            return x

        dx = (x - self.x_prev) * self.freq
        a_d = self._alpha(self.dcutoff)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev

        cutoff = self.mincutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff)
        x_hat = a * x + (1 - a) * self.x_prev

        self.x_prev, self.dx_prev = x_hat, dx_hat
        return x_hat


# ---------------------------------------------------------------- helpers
def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def to_px(lm, w, h):
    return int(lm.x * w), int(lm.y * h)


def _angle(a, b, c):
    """Angle at point b formed by points a-b-c, in degrees. 180 = perfectly straight."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        return 180.0
    cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)
    cos_angle = max(-1.0, min(1.0, cos_angle))
    return math.degrees(math.acos(cos_angle))


def finger_extended(pts, mcp_id, pip_id, tip_id, straight_thresh=155):
    """A (non-thumb) finger is 'extended' if the mcp-pip-tip joint is nearly straight.
    This is robust to hand rotation/tilt, unlike a simple tip-vs-wrist distance check,
    and is what fixes ring/pinky finger misreads that made some finger counts unreliable.
    """
    angle = _angle(pts[mcp_id], pts[pip_id], pts[tip_id])
    return angle > straight_thresh


def thumb_extended(pts):
    """The thumb doesn't bend the same way as the other fingers, so instead of an angle
    test we check how far the thumb tip has splayed away from the palm, using the
    thumb's own base (MCP) as the 'curled' reference distance. This stops the thumb
    from being misread as 'extended' when it's tucked in but naturally sticking out to
    the side -- the main cause of 4-finger shortcuts being swallowed by the open-palm
    freeze gesture.
    """
    tip = pts[4]
    mcp = pts[2]
    pinky_mcp = pts[17]
    return dist(tip, pinky_mcp) > dist(mcp, pinky_mcp) * 1.15


def get_finger_state(pts):
    return {
        "thumb": thumb_extended(pts),
        "index": finger_extended(pts, 5, 6, 8),
        "middle": finger_extended(pts, 9, 10, 12),
        "ring": finger_extended(pts, 13, 14, 16),
        "pinky": finger_extended(pts, 17, 18, 20),
    }


# ---------------------------------------------------------------- calibration
def run_calibration(webcam, hands, mpdraw, mphands):
    """Have the user touch the top-left and bottom-right of their control zone."""
    corners = []
    prompts = ["Point at TOP-LEFT of a COMFORTABLE control area (don't overstretch), press SPACE",
               "Point at BOTTOM-RIGHT of that comfortable area, press SPACE"]

    for prompt in prompts:
        while True:
            success, frame = webcam.read()
            if not success:
                continue
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            index_pt = None
            if result.multi_hand_landmarks:
                lm = result.multi_hand_landmarks[0]
                index_pt = to_px(lm.landmark[8], w, h)
                mpdraw.draw_landmarks(frame, lm, mphands.HAND_CONNECTIONS)
                cv2.circle(frame, index_pt, 12, (255, 0, 255), cv2.FILLED)

            cv2.putText(frame, prompt, (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 255, 255), 2)
            for cx, cy in corners:
                cv2.circle(frame, (cx, cy), 8, (0, 255, 0), cv2.FILLED)

            cv2.imshow("Hand Mouse", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' ') and index_pt is not None:
                corners.append(index_pt)
                break
            if key == 27:  # ESC -> skip calibration, use defaults
                return None

    (x1, y1), (x2, y2) = corners
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def run_measurement_calibration(webcam, hands, mpdraw, mphands):
    """Calibrate the pixel-to-cm ratio for the middle-finger measuring gesture.
    Hold both middle fingertips at a known distance apart (e.g. against a ruler
    or a piece of paper with marked cm), press SPACE, then type the real distance
    into the terminal. ESC cancels and keeps the previous calibration (if any).
    """
    print("[measure] hold BOTH middle fingertips at a known distance apart, "
          "focus the webcam window, then press SPACE (ESC to cancel)")
    px_dist = None
    while True:
        success, frame = webcam.read()
        if not success:
            continue
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        pts_list = []
        if result.multi_hand_landmarks:
            for handlms in result.multi_hand_landmarks:
                pts_list.append([to_px(lm, w, h) for lm in handlms.landmark])
                mpdraw.draw_landmarks(frame, handlms, mphands.HAND_CONNECTIONS)

        cv2.putText(frame, "Hold BOTH middle fingertips at a KNOWN distance, press SPACE",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        current_px = None
        if len(pts_list) == 2:
            p1 = pts_list[0][12]
            p2 = pts_list[1][12]
            current_px = dist(p1, p2)
            cv2.line(frame, p1, p2, (0, 200, 255), 2)
            cv2.putText(frame, f"{current_px:.0f}px", (30, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)

        cv2.imshow("Hand Mouse", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' ') and current_px is not None:
            px_dist = current_px
            break
        if key == 27:
            print("[measure] calibration cancelled")
            return None

    try:
        cm_value = float(input("Enter the real-world distance between your two "
                                "middle fingertips, in cm: "))
        if cm_value <= 0:
            raise ValueError
    except (ValueError, EOFError):
        print("[measure] invalid input, calibration cancelled")
        return None

    return px_dist / cm_value


# ---------------------------------------------------------------- setup
webcam = cv2.VideoCapture(0)
webcam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

mphands = mp.solutions.hands
hands = mphands.Hands(max_num_hands=2, min_detection_confidence=0.7,
                       min_tracking_confidence=0.7)
mpdraw = mp.solutions.drawing_utils

screenW, screenH = pyautogui.size()
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

cv2.namedWindow("Hand Mouse", cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty("Hand Mouse", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

box = run_calibration(webcam, hands, mpdraw, mphands)
if box is None:
    box = (80, 80, 1280 - 80, 720 - 80)  # fallback default
bx1, by1, bx2, by2 = box

filter_x = OneEuroFilter(mincutoff=0.8, beta=0.4)
filter_y = OneEuroFilter(mincutoff=0.8, beta=0.4)

CLICK_DIST = 35
DRAG_HOLD_TIME = 0.25
DWELL_TIME = 1.0
DWELL_RADIUS = 40
ZOOM_COOLDOWN = 0.3
SCREENSHOT_HOLD_TIME = 0.6
SCREENSHOT_COOLDOWN = 2.0
SHORTCUT_HOLD_TIME = 0.8
SWIPE_COOLDOWN = 0.8
SWIPE_MIN_DX = 120
SWIPE_MAX_DT = 0.5
NAV_SWIPE_MIN_DIST = 130
NAV_SWIPE_MAX_DT = 0.5
NAV_SWIPE_COOLDOWN = 0.8
CONFIG_RELOAD_INTERVAL = 2.0

mirrored_mode = False   # 'm' toggles this if controls feel backwards for your setup
dwell_mode = False
show_hud = True
shortcuts_mode = False   # 'g' toggles: hold up 1-4 fingers to fire a configured action
presentation_mode = False  # 'p' toggles: swipe hand left/right to change slides
write_mode = False      # 'w' toggles: air-writing / drawing with the index finger
reach_margin = 0.18     # shrinks the effective control box so screen edges are reachable
                        # without stretching to the physical calibration corners

pinch_start_time = None
is_dragging = False
right_click_locked = False

dwell_pos = None
dwell_start = None

trail = deque(maxlen=15)

prev_zoom_dist = None
last_zoom_time = 0

last_screenshot_time = 0
fist_start_time = None

shortcut_hold_count = None
shortcut_hold_start = None
shortcut_count_history = deque(maxlen=5)   # smooths the 1-4 finger count to avoid flicker

wrist_history = deque(maxlen=6)
last_swipe_time = 0

nav_history = deque(maxlen=6)
last_nav_time = 0

fullscreen_mode = True

draw_canvas = None       # created lazily once we know the frame size; persists ink
last_draw_point = None
px_per_cm = None         # set via 'x' calibration; measuring gesture shows raw px until then

finger_state_debug = None  # last single-hand finger-state reading, for the HUD debug line

gesture_config = load_gesture_config()
last_config_check = time.time()

prev_time = time.time()

# ---------------------------------------------------------------- main loop
while True:
    success, frame = webcam.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (255, 0, 255), 2)

    gesture_label = "idle"
    finger_state_debug = None
    now = time.time()

    # periodically reload the shared config so web-app edits take effect live
    if now - last_config_check > CONFIG_RELOAD_INTERVAL:
        gesture_config = load_gesture_config()
        last_config_check = now

    hands_pts = []
    if result.multi_hand_landmarks:
        for handlms in result.multi_hand_landmarks:
            pts = [to_px(lm, w, h) for lm in handlms.landmark]
            hands_pts.append(pts)
            mpdraw.draw_landmarks(frame, handlms, mphands.HAND_CONNECTIONS)

    # ---------------- two-hand gestures: zoom or cm-measurement ----------------
    if len(hands_pts) == 2:
        fs1 = get_finger_state(hands_pts[0])
        fs2 = get_finger_state(hands_pts[1])
        # measuring gesture = both middle fingers up, index fingers down on both hands,
        # kept distinct from the zoom gesture (both index fingers) so they never clash
        both_middle_only = (fs1["middle"] and fs2["middle"]
                             and not fs1["index"] and not fs2["index"])

        if both_middle_only:
            gesture_label = "measuring"
            p1 = hands_pts[0][12]
            p2 = hands_pts[1][12]
            px_dist = dist(p1, p2)
            cv2.line(frame, p1, p2, (0, 255, 255), 3)
            midpoint = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            if px_per_cm:
                label = f"{px_dist / px_per_cm:.1f} cm"
            else:
                label = f"{int(px_dist)} px (press x to calibrate)"
            cv2.putText(frame, label, midpoint, cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 255, 255), 2)
            prev_zoom_dist = None
        else:
            gesture_label = "zoom"
            p1 = hands_pts[0][8]
            p2 = hands_pts[1][8]
            cur_dist = dist(p1, p2)
            cv2.line(frame, p1, p2, (0, 200, 255), 2)

            if prev_zoom_dist is not None and (now - last_zoom_time) > ZOOM_COOLDOWN:
                delta = cur_dist - prev_zoom_dist
                if abs(delta) > 15:
                    pyautogui.keyDown('ctrl')
                    pyautogui.scroll(40 if delta > 0 else -40)
                    pyautogui.keyUp('ctrl')
                    last_zoom_time = now
            prev_zoom_dist = cur_dist

        is_dragging = False  # safety: never leave a drag hanging
        last_draw_point = None

    # ---------------- single-hand gestures ----------------
    elif len(hands_pts) == 1:
        prev_zoom_dist = None
        pts = hands_pts[0]
        fs = get_finger_state(pts)
        finger_state_debug = fs
        index_tip = pts[8]
        thumb_tip = pts[4]
        middle_tip = pts[12]
        pinky_tip = pts[20]
        wrist = pts[0]

        all_extended = all(fs.values())
        all_curled = not any(fs.values())

        is_nav_pose = (fs["index"] and fs["middle"] and fs["ring"]
                        and fs["pinky"] and not fs["thumb"])
        if not (is_nav_pose and not shortcuts_mode):
            nav_history.clear()


        # ---- FREEZE: open palm, all 5 fingers extended -> lock cursor, cancel any hold-state
        if all_extended:
            gesture_label = "FROZEN (open palm)"
            if is_dragging:
                pyautogui.mouseUp()
                is_dragging = False
            pinch_start_time = None
            right_click_locked = False
            fist_start_time = None
            shortcut_hold_count = None
            shortcut_count_history.clear()
            nav_history.clear()
            last_draw_point = None
            trail.clear()

        # ---- SCREENSHOT: closed fist, held briefly
        elif all_curled:
            gesture_label = "hold for screenshot"
            last_draw_point = None
            if fist_start_time is None:
                fist_start_time = now
            elif (now - fist_start_time) > SCREENSHOT_HOLD_TIME:
                if (now - last_screenshot_time) > SCREENSHOT_COOLDOWN:
                    take_screenshot()
                    last_screenshot_time = now
                    gesture_label = "SCREENSHOT!"
                fist_start_time = now + 999  # cooldown until fist released

        # ---- WRITE MODE: point with index finger to draw, pinch to lift the pen
        elif write_mode:
            fist_start_time = None
            shortcut_hold_count = None
            pinch_dist = dist(index_tip, thumb_tip)
            pen_down = fs["index"] and pinch_dist >= CLICK_DIST

            if draw_canvas is None:
                draw_canvas = np.zeros((h, w, 3), dtype=np.uint8)

            if pen_down:
                gesture_label = "writing"
                if last_draw_point is not None:
                    cv2.line(draw_canvas, last_draw_point, index_tip,
                              (0, 255, 255), 4, cv2.LINE_AA)
                last_draw_point = index_tip
                cv2.circle(frame, index_tip, 8, (0, 255, 255), cv2.FILLED)
            else:
                gesture_label = "pen up" if pinch_dist < CLICK_DIST else "write mode (point to draw)"
                last_draw_point = None

        # ---- SHORTCUTS MODE: hold up 1-4 fingers to fire a configured action
        elif shortcuts_mode:
            fist_start_time = None
            raw_count = sum([fs["index"], fs["middle"], fs["ring"], fs["pinky"]])
            shortcut_count_history.append(raw_count)
            # majority vote over recent frames so one noisy reading can't reset the hold timer
            stable_count = max(set(shortcut_count_history), key=shortcut_count_history.count)

            if stable_count in (1, 2, 3, 4):
                gesture_label = f"shortcut: hold {stable_count} finger(s)"
                if shortcut_hold_count != stable_count:
                    shortcut_hold_count = stable_count
                    shortcut_hold_start = now
                else:
                    elapsed = now - shortcut_hold_start
                    if elapsed > SHORTCUT_HOLD_TIME:
                        action = gesture_config.get(str(stable_count))
                        label = action.get("label", action.get("value", "")) if action else "?"
                        run_action(action)
                        gesture_label = f"launched: {label}"
                        shortcut_hold_start = now + 999  # cooldown until finger count changes
            else:
                shortcut_hold_count = None

        # ---- PRESENTATION MODE: swipe left/right to change slides
        elif presentation_mode:
            fist_start_time = None
            wrist_history.append((wrist[0], now))
            if len(wrist_history) >= 2:
                dx = wrist_history[-1][0] - wrist_history[0][0]
                dt = wrist_history[-1][1] - wrist_history[0][1]
                if 0 < dt < SWIPE_MAX_DT and (now - last_swipe_time) > SWIPE_COOLDOWN:
                    if dx > SWIPE_MIN_DX:
                        pyautogui.press('right')
                        gesture_label = "next slide"
                        last_swipe_time = now
                        wrist_history.clear()
                    elif dx < -SWIPE_MIN_DX:
                        pyautogui.press('left')
                        gesture_label = "previous slide"
                        last_swipe_time = now
                        wrist_history.clear()
            cv2.circle(frame, wrist, 10, (0, 255, 255), cv2.FILLED)

        # ---- NAV SWIPE: 4 fingers up (thumb tucked), swipe to switch tabs or minimize.
        # Only active while shortcuts_mode is off, so it never fights your 1-4 finger
        # app-shortcuts (which also use a 4-finger hold, just without caring about swipe).
        elif (not shortcuts_mode and fs["index"] and fs["middle"] and fs["ring"]
              and fs["pinky"] and not fs["thumb"]):
            fist_start_time = None
            gesture_label = "nav gesture"
            nav_history.append((wrist[0], wrist[1], now))
            if len(nav_history) >= 2:
                dx = nav_history[-1][0] - nav_history[0][0]
                dy = nav_history[-1][1] - nav_history[0][1]
                dt = nav_history[-1][2] - nav_history[0][2]
                if 0 < dt < NAV_SWIPE_MAX_DT and (now - last_nav_time) > NAV_SWIPE_COOLDOWN:
                    if abs(dx) > abs(dy) and abs(dx) > NAV_SWIPE_MIN_DIST:
                        if dx > 0:
                            pyautogui.hotkey('ctrl', 'tab')
                            gesture_label = "next tab"
                        else:
                            pyautogui.hotkey('ctrl', 'shift', 'tab')
                            gesture_label = "previous tab"
                        last_nav_time = now
                        nav_history.clear()
                    elif abs(dy) > abs(dx) and dy > NAV_SWIPE_MIN_DIST:
                        minimize_active_window()
                        gesture_label = "minimize"
                        last_nav_time = now
                        nav_history.clear()
            cv2.circle(frame, wrist, 10, (0, 200, 255), cv2.FILLED)

        # ---- SCROLL: index + middle up, ring + pinky down
        elif fs["index"] and fs["middle"] and not fs["ring"] and not fs["pinky"]:
            fist_start_time = None
            gesture_label = "scroll"
            avg_y = (index_tip[1] + middle_tip[1]) / 2
            if trail:
                dy = trail[-1][1] - avg_y
                if abs(dy) > 2:
                    pyautogui.scroll(int(dy * 2))
            trail.append((int(index_tip[0]), int(avg_y)))

        # ---- VOLUME: thumb + pinky out, index + middle curled (ring ignored -- see docstring)
        elif fs["thumb"] and fs["pinky"] and not fs["index"] and not fs["middle"]:
            fist_start_time = None
            nav_history.clear()
            gesture_label = "volume"
            d = dist(thumb_tip, pinky_tip)
            level = np.interp(d, (30, 250), (0.0, 1.0))
            level = max(0.0, min(1.0, level))
            cv2.line(frame, thumb_tip, pinky_tip, (0, 255, 0), 3)
            cv2.putText(frame, f"Volume {int(level * 100)}%", (30, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            set_system_volume(level)

        # ---- DEFAULT: cursor + click/drag/right-click
        else:
            fist_start_time = None
            gesture_label = "cursor"
            mx = (bx2 - bx1) * reach_margin
            my = (by2 - by1) * reach_margin
            ex1, ex2 = bx1 + mx, bx2 - mx
            ey1, ey2 = by1 + my, by2 - my

            mouseX = np.interp(index_tip[0], (ex1, ex2), (0, screenW))
            mouseY = np.interp(index_tip[1], (ey1, ey2), (0, screenH))
            if mirrored_mode:
                mouseX = screenW - mouseX

            clocX = filter_x.filter(mouseX)
            clocY = filter_y.filter(mouseY)
            clocX = max(0, min(screenW - 1, clocX))
            clocY = max(0, min(screenH - 1, clocY))

            if not dwell_mode:
                pyautogui.moveTo(clocX, clocY)

            # left click / drag via thumb-index pinch
            pinch_dist = dist(index_tip, thumb_tip)
            if pinch_dist < CLICK_DIST:
                if pinch_start_time is None:
                    pinch_start_time = now
                elif not is_dragging and (now - pinch_start_time) > DRAG_HOLD_TIME:
                    is_dragging = True
                    pyautogui.mouseDown()
                    gesture_label = "drag"
                if is_dragging:
                    pyautogui.moveTo(clocX, clocY)
                    gesture_label = "drag"
            else:
                if pinch_start_time is not None and not is_dragging:
                    pyautogui.click()
                    gesture_label = "click"
                if is_dragging:
                    pyautogui.mouseUp()
                    is_dragging = False
                pinch_start_time = None

            # right click via thumb-middle pinch
            right_dist = dist(middle_tip, thumb_tip)
            if right_dist < CLICK_DIST:
                if not right_click_locked:
                    pyautogui.click(button='right')
                    right_click_locked = True
                    gesture_label = "right click"
            else:
                right_click_locked = False

            # dwell click (accessibility mode)
            if dwell_mode:
                pyautogui.moveTo(clocX, clocY)
                if dwell_pos is None or dist((clocX, clocY), dwell_pos) > DWELL_RADIUS:
                    dwell_pos = (clocX, clocY)
                    dwell_start = now
                else:
                    elapsed = now - dwell_start
                    progress = min(1.0, elapsed / DWELL_TIME)
                    cv2.ellipse(frame, index_tip, (20, 20), 0, 0, int(360 * progress),
                                (0, 255, 255), 3)
                    if progress >= 1.0:
                        pyautogui.click()
                        gesture_label = "dwell click"
                        dwell_start = now + 999  # cooldown until finger moves away

            trail.append(index_tip)
            cv2.circle(frame, index_tip, 10, (255, 0, 255), cv2.FILLED)

    else:
        pinch_start_time = None
        if is_dragging:
            pyautogui.mouseUp()
            is_dragging = False
        prev_zoom_dist = None
        fist_start_time = None
        shortcut_hold_count = None
        shortcut_count_history.clear()
        last_draw_point = None
        wrist_history.clear()
        nav_history.clear()

    # cursor trail (visual feedback on the webcam feed only)
    for i, p in enumerate(trail):
        alpha = (i + 1) / len(trail)
        pt = (int(p[0]), int(p[1]))
        cv2.circle(frame, pt, int(4 * alpha) + 2, (255, 0, 255), cv2.FILLED)

    # write-mode ink overlay -- drawn regardless of mode so it stays visible until erased
    if draw_canvas is not None:
        mask = draw_canvas.any(axis=2)
        frame[mask] = draw_canvas[mask]

    # voice commands
    if voice_enabled and voice_commands:
        cmd = voice_commands.popleft()
        if "right click" in cmd:
            pyautogui.click(button='right')
        elif "click" in cmd:
            pyautogui.click()
        elif "scroll up" in cmd:
            pyautogui.scroll(200)
        elif "scroll down" in cmd:
            pyautogui.scroll(-200)
        elif "screenshot" in cmd:
            take_screenshot()

    # HUD
    if show_hud:
        fps = 1 / max(now - prev_time, 1e-6)
        prev_time = now
        cv2.putText(frame, f"gesture: {gesture_label}", (30, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"FPS: {int(fps)}", (30, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        if finger_state_debug is not None:
            dbg = " ".join(f"{k[0].upper()}:{'1' if v else '0'}"
                            for k, v in finger_state_debug.items())
            cv2.putText(frame, dbg, (30, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
        modes = (f"mirror:{mirrored_mode} dwell:{dwell_mode} voice:{voice_enabled} "
                 f"shortcuts:{shortcuts_mode} present:{presentation_mode} write:{write_mode} "
                 f"reach:{int(reach_margin*100)}% cm-cal:{'yes' if px_per_cm else 'no'} "
                 f"fullscreen:{fullscreen_mode}")
        cv2.putText(frame, modes, (30, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 0), 2)

    cv2.imshow("Hand Mouse", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('c'):
        new_box = run_calibration(webcam, hands, mpdraw, mphands)
        if new_box is not None:
            bx1, by1, bx2, by2 = new_box
    elif key == ord('m'):
        mirrored_mode = not mirrored_mode
    elif key == ord('d'):
        dwell_mode = not dwell_mode
        dwell_pos = None
    elif key == ord('h'):
        show_hud = not show_hud
    elif key == ord('g'):
        shortcuts_mode = not shortcuts_mode
        presentation_mode = False
        write_mode = False
        shortcut_hold_count = None
        shortcut_count_history.clear()
        nav_history.clear()
    elif key == ord('p'):
        presentation_mode = not presentation_mode
        shortcuts_mode = False
        write_mode = False
        wrist_history.clear()
    elif key == ord('w'):
        write_mode = not write_mode
        shortcuts_mode = False
        presentation_mode = False
        shortcut_hold_count = None
        shortcut_count_history.clear()
        wrist_history.clear()
        last_draw_point = None
    elif key == ord('e'):
        if draw_canvas is not None:
            draw_canvas[:] = 0
        print("[write] canvas cleared")
    elif key == ord('s'):
        if draw_canvas is not None and draw_canvas.any():
            save_drawing(draw_canvas)
        else:
            print("[write] nothing to save yet")
    elif key == ord('x'):
        calibrated = run_measurement_calibration(webcam, hands, mpdraw, mphands)
        if calibrated:
            px_per_cm = calibrated
            print(f"[measure] calibrated: {px_per_cm:.2f} px/cm")
    elif key == ord('f'):
        fullscreen_mode = not fullscreen_mode
        prop = cv2.WINDOW_FULLSCREEN if fullscreen_mode else cv2.WINDOW_NORMAL
        cv2.setWindowProperty("Hand Mouse", cv2.WND_PROP_FULLSCREEN, prop)
    elif key == ord('r'):
        gesture_config = load_gesture_config()
        last_config_check = now
        print("[config] reloaded")
    elif key == ord('v'):
        if VOICE_LIB_AVAILABLE:
            voice_enabled = not voice_enabled
            if voice_enabled:
                threading.Thread(target=_voice_listener, daemon=True).start()
        else:
            print("Voice commands need: pip install SpeechRecognition pyaudio")
    elif key == ord('['):
        reach_margin = max(0.0, reach_margin - 0.03)
    elif key == ord(']'):
        reach_margin = min(0.45, reach_margin + 0.03)

if is_dragging:
    pyautogui.mouseUp()

webcam.release()
cv2.destroyAllWindows()