// Express backend for the gesture-configuration website.
//
// Reads/writes a single JSON file that hand_mouse.py also reads directly --
// no database. By default that file lives two folders up from this file
// (i.e. next to hand_mouse.py, assuming this project sits in a
// "gesture-config-web" folder alongside hand_mouse.py). Override with the
// CONFIG_FILE_PATH env var if your layout is different.

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;
const CONFIG_FILE_PATH =
  process.env.CONFIG_FILE_PATH || path.join(__dirname, '..', '..', 'gestures_config.json');

app.use(cors());
app.use(express.json());

const DEFAULT_CONFIG = {
  1: { type: 'app', value: 'chrome', label: 'Chrome' },
  2: { type: 'app', value: 'vscode', label: 'VS Code' },
  3: { type: 'app', value: 'calculator', label: 'Calculator' },
  4: { type: 'app', value: 'explorer', label: 'File Explorer' },
};

const VALID_TYPES = ['app', 'website', 'shortcut', 'media', 'screenshot'];
const KNOWN_APPS = ['chrome', 'vscode', 'calculator', 'explorer', 'notepad'];
const MEDIA_ACTIONS = ['playpause', 'next', 'prev', 'volume_up', 'volume_down', 'mute'];

function readConfig() {
  try {
    if (!fs.existsSync(CONFIG_FILE_PATH)) return { ...DEFAULT_CONFIG };
    const raw = fs.readFileSync(CONFIG_FILE_PATH, 'utf-8');
    return { ...DEFAULT_CONFIG, ...JSON.parse(raw) };
  } catch (err) {
    console.error('Failed to read config, returning defaults:', err.message);
    return { ...DEFAULT_CONFIG };
  }
}

function writeConfig(config) {
  fs.writeFileSync(CONFIG_FILE_PATH, JSON.stringify(config, null, 2), 'utf-8');
}

function validateSlot(slot) {
  if (!slot || typeof slot !== 'object') return 'Slot must be an object';
  if (!VALID_TYPES.includes(slot.type)) return `type must be one of ${VALID_TYPES.join(', ')}`;
  if (typeof slot.value !== 'string' || slot.value.trim() === '') return 'value is required';
  if (slot.type === 'app' && !KNOWN_APPS.includes(slot.value) && !slot.value.includes('\\') && !slot.value.includes('/')) {
    // allow known app keys OR a raw path -- otherwise warn but don't hard-block
  }
  if (slot.type === 'media' && !MEDIA_ACTIONS.includes(slot.value)) {
    return `media value must be one of ${MEDIA_ACTIONS.join(', ')}`;
  }
  return null;
}

// GET current config + metadata the UI needs to render dropdowns
app.get('/api/gestures', (req, res) => {
  res.json({
    config: readConfig(),
    meta: {
      slots: [1, 2, 3, 4],
      types: VALID_TYPES,
      knownApps: KNOWN_APPS,
      mediaActions: MEDIA_ACTIONS,
      configFilePath: CONFIG_FILE_PATH,
    },
  });
});

// PUT full replacement of the 4 gesture slots
app.put('/api/gestures', (req, res) => {
  const incoming = req.body || {};
  const next = {};

  for (const slotNum of [1, 2, 3, 4]) {
    const slot = incoming[String(slotNum)];
    if (!slot) continue; // leave unspecified slots untouched via merge below
    const error = validateSlot(slot);
    if (error) {
      return res.status(400).json({ error: `Slot ${slotNum}: ${error}` });
    }
    next[slotNum] = {
      type: slot.type,
      value: slot.value.trim(),
      label: (slot.label || slot.value).trim(),
    };
  }

  const merged = { ...readConfig(), ...next };
  try {
    writeConfig(merged);
    res.json({ config: merged });
  } catch (err) {
    res.status(500).json({ error: `Failed to write config: ${err.message}` });
  }
});

app.get('/api/health', (req, res) => {
  res.json({ ok: true, configFilePath: CONFIG_FILE_PATH });
});

app.listen(PORT, () => {
  console.log(`Gesture config server running on http://localhost:${PORT}`);
  console.log(`Reading/writing config at: ${CONFIG_FILE_PATH}`);
});
