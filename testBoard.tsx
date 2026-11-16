import React, { useState, type CSSProperties } from "react";
import SprinklerCard from "./SprinklerCard";

type DisplayOption = "SprinklerCard" | "Clock" | "Weather" | "Calendar" | "Reports";

interface Panel {
  id: number;
  display: DisplayOption | "";
  height: number; 
}

const DISPLAY_OPTIONS: DisplayOption[] = ["SprinklerCard", "Clock", "Weather", "Calendar", "Reports"];

const DISPLAY_COMPONENTS: Partial<Record<DisplayOption, () => React.ReactNode>> = {
  SprinklerCard: () => <SprinklerCard />,
};

const INITIAL_PANELS: Panel[] = [
  { id: 1, display: "", height: 105 },
  { id: 2, display: "", height: 150 },
  { id: 3, display: "", height: 100 },
  { id: 4, display: "", height: 122 },
];

const DEFAULT_PANEL_HEIGHT = 110;

interface DisplayPickerProps {
  value: Panel["display"];
  onChange: (value: Panel["display"]) => void;
  compact?: boolean; 
}

const DisplayPicker: React.FC<DisplayPickerProps> = ({ value, onChange, compact }) => (
  <select
    aria-label="Choose display"
    value={value}
    onChange={(e) => onChange(e.target.value as Panel["display"])}
    style={compact ? { ...styles.select, ...styles.selectCompact } : styles.select}
  >
    <option value="">choose Display</option>
    {DISPLAY_OPTIONS.map((opt) => (
      <option key={opt} value={opt}>
        {opt}
      </option>
    ))}
  </select>
);

const PaintBucketIcon: React.FC = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="m19 11-8-8-8.6 8.6a2 2 0 0 0 0 2.8l5.2 5.2c.8.8 2 .8 2.8 0L19 11Z" />
    <path d="m5 2 5 5" />
    <path d="M2 13h15" />
    <circle cx="21" cy="19" r="1.6" fill="#000" />
  </svg>
);

const DisplayTemplate: React.FC = () => {
  const [panels, setPanels] = useState<Panel[]>(INITIAL_PANELS);
  const [background, setBackground] = useState<string>("#00968b");

  const updatePanel = (id: number, display: Panel["display"]): void =>
    setPanels((prev) => prev.map((p) => (p.id === id ? { ...p, display } : p)));

  const addPanel = (): void =>
    setPanels((prev) => [
      ...prev,
      { id: Date.now(), display: "", height: DEFAULT_PANEL_HEIGHT },
    ]);

  return (
    <div style={styles.stage}>
      <div style={{ ...styles.screen, background }}>
        <label style={styles.paintButton} title="Change background colour">
          <PaintBucketIcon />
          <input
            type="color"
            value={background}
            onChange={(e) => setBackground(e.target.value)}
            style={styles.hiddenInput}
            aria-label="Background colour"
          />
        </label>

        {/* Panels */}
        <div style={styles.list}>
          {panels.map((panel) => {
            const content = panel.display ? DISPLAY_COMPONENTS[panel.display]?.() : null;

            return (
              <section
                key={panel.id}
                style={
                  content
                    ? { ...styles.card, ...styles.cardFilled, height: panel.height }
                    : { ...styles.card, minHeight: panel.height }
                }
              >
                {content && <div style={styles.cardFill}>{content}</div>}

                <DisplayPicker
                  value={panel.display}
                  onChange={(v) => updatePanel(panel.id, v)}
                  compact={!!content}
                />

                {panel.display && !content && <div style={styles.cardBody}>{panel.display}</div>}
              </section>
            );
          })}
        </div>

        <button type="button" onClick={addPanel} style={styles.addButton} aria-label="Add panel">
          <svg width="22" height="22" viewBox="0 0 24 24" stroke={background} strokeWidth="3" strokeLinecap="round" aria-hidden="true">
            <path d="M12 3v18M3 12h18" />
          </svg>
        </button>
      </div>
    </div>
  );
};

/* ---------- Styles ---------- */

const styles: Record<string, CSSProperties> = {
  stage: {
    minHeight: "100vh",
    background: "#1e1e1e",
    display: "flex",
    justifyContent: "center",
    padding: 24,
    boxSizing: "border-box",
    fontFamily: "Inter, system-ui, sans-serif",
  },
  screen: {
    position: "relative",
    width: 397,
    maxWidth: "100%",
    minHeight: 694,
    padding: "110px 20px 70px",
    boxSizing: "border-box",
  },
  paintButton: {
    position: "absolute",
    top: 12,
    right: 18,
    cursor: "pointer",
    display: "flex",
  },
  hiddenInput: {
    position: "absolute",
    inset: 0,
    opacity: 0,
    width: "100%",
    height: "100%",
    cursor: "pointer",
  },
  list: {
    display: "flex",
    flexDirection: "column",
    gap: 18,
  },
  card: {
    background: "#d9d9d9",
    padding: "9px 12px",
    boxSizing: "border-box",
  },
  // NEW: used when a real widget is showing. It needs a fixed height so the
  // SprinklerCard has something to fill, and no padding so it goes edge to edge.
  cardFilled: {
    position: "relative",
    padding: 0,
    overflow: "hidden",
  },
  cardFill: {
    position: "absolute",
    inset: 0,
  },
  select: {
    background: "#fff",
    border: "none",
    fontSize: 20,
    padding: "4px 8px",
    minWidth: 227,
    color: "#000",
    cursor: "pointer",
  },
  // ICONS
  selectCompact: {
    position: "absolute",
    left: 8,
    bottom: 8,
    zIndex: 2,
    fontSize: 12,
    minWidth: 0,
    padding: "3px 6px",
    opacity: 0.85,
  },
  cardBody: {
    marginTop: 12,
    fontSize: 18,
    color: "#333",
  },
  addButton: {
    position: "absolute",
    right: 34,
    bottom: 14,
    width: 32,
    height: 32,
    borderRadius: 8,
    border: "none",
    background: "#000",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    padding: 0,
  },
};

export default DisplayTemplate;
