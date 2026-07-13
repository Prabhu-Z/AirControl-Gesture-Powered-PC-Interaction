import React, { useEffect, useState } from 'react';

const TYPE_LABELS = {
  app: 'Open application',
  website: 'Open website',
  shortcut: 'Keyboard shortcut',
  media: 'Media control',
  screenshot: 'Take screenshot',
};

const APP_OPTIONS = [
  { value: 'chrome', label: 'Chrome' },
  { value: 'vscode', label: 'VS Code' },
  { value: 'calculator', label: 'Calculator' },
  { value: 'explorer', label: 'File Explorer' },
  { value: 'notepad', label: 'Notepad' },
];

const MEDIA_OPTIONS = [
  { value: 'playpause', label: 'Play / Pause' },
  { value: 'next', label: 'Next track' },
  { value: 'prev', label: 'Previous track' },
  { value: 'volume_up', label: 'Volume up' },
  { value: 'volume_down', label: 'Volume down' },
  { value: 'mute', label: 'Mute' },
];

// tiny hand glyph showing how many fingers are raised for this slot
function HandGlyph({ count }) {
  const fingers = [1, 2, 3, 4];
  return (
    <svg width="40" height="48" viewBox="0 0 40 48" aria-hidden="true">
      <rect x="10" y="24" width="20" height="20" rx="8" fill="#2a2f3d" />
      {fingers.map((f, i) => {
        const up = f <= count;
        const x = 6 + i * 8;
        return (
          <rect
            key={f}
            x={x}
            y={up ? 4 : 20}
            width="6"
            height={up ? 24 : 8}
            rx="3"
            fill={up ? '#ff5fd6' : '#2a2f3d'}
          />
        );
      })}
    </svg>
  );
}

function emptySlot() {
  return { type: 'app', value: 'chrome', label: '' };
}

export default function App() {
  const [config, setConfig] = useState(null);
  const [meta, setMeta] = useState(null);
  const [status, setStatus] = useState(null); // { kind: 'ok'|'error', message }
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch('/api/gestures')
      .then((r) => r.json())
      .then((data) => {
        setConfig(data.config);
        setMeta(data.meta);
      })
      .catch(() => setStatus({ kind: 'error', message: "Couldn't reach the config server. Is it running?" }));
  }, []);

  function updateSlot(slotNum, patch) {
    setConfig((prev) => ({
      ...prev,
      [slotNum]: { ...(prev[slotNum] || emptySlot()), ...patch },
    }));
  }

  function handleTypeChange(slotNum, type) {
    const defaults = {
      app: { value: 'chrome' },
      website: { value: 'https://' },
      shortcut: { value: 'ctrl+shift+esc' },
      media: { value: 'playpause' },
      screenshot: { value: 'screenshot' },
    };
    updateSlot(slotNum, { type, ...defaults[type] });
  }

  async function handleSave() {
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch('/api/gestures', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Save failed');
      setConfig(data.config);
      setStatus({ kind: 'ok', message: 'Saved. The gesture app picks this up within a couple seconds, or press r there to reload now.' });
    } catch (err) {
      setStatus({ kind: 'error', message: err.message });
    } finally {
      setSaving(false);
    }
  }

  if (!config || !meta) {
    return (
      <div className="app-shell">
        <div className="loading">{status ? status.message : 'Loading gesture map…'}</div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="header">
        <div className="eyebrow">GESTURE SHORTCUTS · hackzen</div>
        <h1>Map fingers to actions</h1>
        <p className="subhead">
          Hold up 1–4 fingers in shortcut mode to fire the matching action below. Changes save straight
          to the file the desktop app reads from.
        </p>
      </header>

      <div className="slots">
        {[1, 2, 3, 4].map((slotNum) => {
          const slot = config[slotNum] || emptySlot();
          return (
            <div className="slot-card" key={slotNum}>
              <div className="slot-head">
                <HandGlyph count={slotNum} />
                <div>
                  <div className="slot-count">{slotNum} finger{slotNum > 1 ? 's' : ''}</div>
                </div>
              </div>

              <label className="field">
                <span>Action type</span>
                <select
                  value={slot.type}
                  onChange={(e) => handleTypeChange(slotNum, e.target.value)}
                >
                  {meta.types.map((t) => (
                    <option key={t} value={t}>
                      {TYPE_LABELS[t] || t}
                    </option>
                  ))}
                </select>
              </label>

              {slot.type === 'app' && (
                <label className="field">
                  <span>Application</span>
                  <select value={slot.value} onChange={(e) => updateSlot(slotNum, { value: e.target.value })}>
                    {APP_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {slot.type === 'website' && (
                <label className="field">
                  <span>URL</span>
                  <input
                    type="text"
                    value={slot.value}
                    placeholder="https://example.com"
                    onChange={(e) => updateSlot(slotNum, { value: e.target.value })}
                  />
                </label>
              )}

              {slot.type === 'shortcut' && (
                <label className="field">
                  <span>Keys (joined with +)</span>
                  <input
                    type="text"
                    value={slot.value}
                    placeholder="ctrl+shift+esc"
                    onChange={(e) => updateSlot(slotNum, { value: e.target.value })}
                  />
                </label>
              )}

              {slot.type === 'media' && (
                <label className="field">
                  <span>Media action</span>
                  <select value={slot.value} onChange={(e) => updateSlot(slotNum, { value: e.target.value })}>
                    {MEDIA_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {slot.type === 'screenshot' && (
                <div className="static-note">No extra input needed — takes a screenshot.</div>
              )}

              <label className="field">
                <span>Label (shown on the HUD)</span>
                <input
                  type="text"
                  value={slot.label || ''}
                  placeholder="e.g. Chrome"
                  onChange={(e) => updateSlot(slotNum, { label: e.target.value })}
                />
              </label>
            </div>
          );
        })}
      </div>

      <div className="save-row">
        <button className="save-btn" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
        {status && <div className={`status ${status.kind}`}>{status.message}</div>}
      </div>

      <footer className="footer">
        Config file: <code>{meta.configFilePath}</code>
      </footer>
    </div>
  );
}
