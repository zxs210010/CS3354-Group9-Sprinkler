import { useState } from "react";

type Props = {
  initialOn?: boolean;
  initialAuto?: boolean;
  onToggle?: (on: boolean) => void;
  onAutoChange?: (auto: boolean) => void;
};

function SprinklerIcon({ color }: { color: string }) {
  const dots: [number, number][] = [
    [50, 12], [50, 30], [50, 48],
    [34, 40], [66, 40],
    [20, 28], [80, 28],
  ];
  return (
    <svg viewBox="0 0 100 100" width="58%" height="58%" aria-hidden="true">
      {dots.map(([cx, cy], index) => (
        <circle key={index} cx={cx} cy={cy} r={5} fill={color} />
      ))}
      <rect x="28" y="64" width="44" height="10" rx="5" fill={color} />
      <rect x="45" y="64" width="10" height="28" rx="5" fill={color} />
    </svg>
  );
}

export default function SprinklerCard({
  initialOn = false,
  initialAuto = false,
  onToggle,
  onAutoChange,
}: Props) {
  const [on, setOn] = useState(initialOn);
  const [auto, setAuto] = useState(initialAuto);

  const flipOn = () => {
    const next = !on;
    setOn(next);
    onToggle?.(next);
  };
  const flipAuto = () => {
    const next = !auto;
    setAuto(next);
    onAutoChange?.(next);
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        boxSizing: "border-box",
        containerType: "inline-size",
        position: "relative",
        padding: "6% 7%",
        background: "linear-gradient(180deg, #a5b4fc 0%, #bbf7b0 100%)",
        fontFamily: '"Zilla Slab", "Roboto Slab", Georgia, serif',
        color: "#000",
        overflow: "hidden",
      }}
    >
      <div style={{ fontSize: "clamp(16px, 8cqw, 44px)", maxWidth: "62%" }}>
        Sprinkler Status: {on ? "ON" : "OFF"}
      </div>

      <button
        type="button"
        onClick={flipOn}
        aria-pressed={on}
        aria-label={on ? "Turn sprinkler off" : "Turn sprinkler on"}
        style={{
          position: "absolute",
          right: "7%",
          top: "50%",
          transform: "translateY(-62%)",
          width: "22%",
          aspectRatio: "1 / 1",
          borderRadius: "50%",
          border: "1px solid #000",
          cursor: "pointer",
          display: "grid",
          placeItems: "center",
          padding: 0,
          background: on ? "#a3e4a0" : "#8e9bb0",
          transition: "background 0.25s",
        }}
      >
        <SprinklerIcon color={on ? "#0b3d0b" : "#000"} />
      </button>

      <div
        style={{
          position: "absolute",
          right: "4%",
          bottom: "5%",
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: "clamp(14px, 6.5cqw, 34px)",
        }}
      >
        <span>Auto</span>
        <button
          type="button"
          role="switch"
          aria-checked={auto}
          aria-label="Auto mode"
          onClick={flipAuto}
          style={{
            width: "2.1em",
            height: "1.15em",
            borderRadius: "1em",
            border: "none",
            background: "#000",
            position: "relative",
            cursor: "pointer",
            padding: 0,
          }}
        >
          <span
            style={{
              position: "absolute",
              top: "0.13em",
              left: auto ? "1.08em" : "0.13em",
              width: "0.89em",
              height: "0.89em",
              borderRadius: "50%",
              background: "#fff",
              transition: "left 0.2s",
            }}
          />
        </button>
      </div>
    </div>
  );
}