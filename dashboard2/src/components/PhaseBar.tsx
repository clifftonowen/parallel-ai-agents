interface Props {
  label: string;
  state: "done" | "active" | "pending";
}

const COLORS = {
  done: "#22c55e",
  active: "#6366f1",
  pending: "#1e293b",
};
const TEXT_COLORS = {
  done: "#fff",
  active: "#fff",
  pending: "#475569",
};

export default function PhaseBar({ label, state }: Props) {
  return (
    <div
      style={{
        flex: 1,
        backgroundColor: COLORS[state],
        borderRadius: 8,
        height: 44,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "0 8px",
        border: state === "active" ? "1px solid #818cf8" : "1px solid transparent",
        transition: "background-color 0.3s",
      }}
    >
      {state === "active" && (
        <span
          style={{
            width: 12,
            height: 12,
            borderRadius: "50%",
            border: "2px solid rgba(255,255,255,0.4)",
            borderTopColor: "#fff",
            display: "inline-block",
            animation: "spin 0.8s linear infinite",
          }}
        />
      )}
      <span
        style={{
          color: TEXT_COLORS[state],
          fontSize: 11,
          fontWeight: 600,
          textAlign: "center",
        }}
      >
        {label}
      </span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
