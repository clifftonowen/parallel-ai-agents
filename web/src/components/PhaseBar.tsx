import { c, font, size } from "../theme";

interface Props {
  label: string;
  state: "done" | "active" | "pending";
}

const COLORS = {
  done: c.reagentSoft,
  active: c.reagent,
  pending: c.paperCard,
};
const TEXT_COLORS = {
  done: c.paper,
  active: c.paper,
  pending: c.inkFaint,
};

export default function PhaseBar({ label, state }: Props) {
  return (
    <div
      style={{
        flex: 1,
        backgroundColor: COLORS[state],
        height: 44,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "0 8px",
        border: state === "pending" ? `1px solid ${c.ruleSoft}` : "1px solid transparent",
        transition: "background-color 0.3s",
      }}
      className={state === "active" ? "animate-pulse" : undefined}
    >
      {state === "active" && (
        <span
          style={{
            width: 12,
            height: 12,
            borderRadius: "50%",
            border: "2px solid rgba(241,236,224,0.4)",
            borderTopColor: c.paper,
            display: "inline-block",
            animation: "spin 0.8s linear infinite",
          }}
        />
      )}
      <span
        style={{
          color: TEXT_COLORS[state],
          fontFamily: font.mono,
          fontSize: size.micro,
          fontWeight: 700,
          letterSpacing: "0.04em",
          textAlign: "center",
        }}
      >
        {label}
      </span>
    </div>
  );
}
