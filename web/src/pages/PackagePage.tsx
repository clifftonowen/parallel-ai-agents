import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { downloadZip, getRun } from "../api/client";
import MaterialViewer, { type Material } from "../components/MaterialViewer";
import type { OutputPaths, RunState } from "../types";
import { c, font, eyebrow, hairline, layout, size, space, display } from "../theme";

const basename = (p: string) => p.split(/[\\/]/).pop() ?? p;

// Build the three learner-facing materials from the raw outputs. PDFs are NOT their
// own rows — they're just another way to download the notes or flashcards.
function buildMaterials(outputs: OutputPaths): Material[] {
  const out: Material[] = [];

  if (outputs.notes_md) {
    const downloads = [{ label: "Markdown", filename: basename(outputs.notes_md) }];
    if (outputs.notes_pdf) downloads.push({ label: "PDF (print)", filename: basename(outputs.notes_pdf) });
    out.push({
      key: "notes",
      title: "Notes",
      blurb: "The topic, written out clearly — read it start to finish.",
      kind: "doc",
      sourceFilename: basename(outputs.notes_md),
      downloads,
    });
  }

  if (outputs.flashcards_md) {
    const downloads = [{ label: "Markdown", filename: basename(outputs.flashcards_md) }];
    if (outputs.flashcards_pdf)
      downloads.push({ label: "PDF (print)", filename: basename(outputs.flashcards_pdf) });
    out.push({
      key: "flashcards",
      title: "Flashcards",
      blurb: "Question-and-answer prompts to test what stuck.",
      kind: "doc",
      sourceFilename: basename(outputs.flashcards_md),
      downloads,
    });
  }

  if (outputs.video) {
    out.push({
      key: "video",
      title: "Video",
      blurb: "A short narrated walkthrough with slides.",
      kind: "video",
      sourceFilename: basename(outputs.video),
      downloads: [{ label: "Video (mp4)", filename: basename(outputs.video) }],
    });
  }

  return out;
}

export default function PackagePage() {
  const { run_id } = useParams<{ run_id?: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunState | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<Material | null>(null);

  useEffect(() => {
    if (!run_id) return;
    getRun(run_id)
      .then(setRun)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Couldn't load your materials."))
      .finally(() => setLoading(false));
  }, [run_id]);

  const materials = useMemo(() => (run ? buildMaterials(run.outputs) : []), [run]);

  if (loading) return <Centered>Opening your study materials…</Centered>;
  if (err || !run) return <Centered tone="flag">{err ?? "Nothing to show here."}</Centered>;

  return (
    <main style={page}>
      <header style={headRow}>
        <button onClick={() => navigate("/")} style={backLink}>
          ← new topic
        </button>
        <div style={headRight}>
          <div style={{ ...eyebrow, color: c.reagent }}>· ready to study</div>
          {/* The timing and token numbers for this run. Only runs started
              through benchmark_profile.py carry a report, so this is a link
              rather than an inline panel. */}
          <button onClick={() => navigate(`/benchmark/${run.run_id}`)} style={benchLink}>
            benchmark →
          </button>
        </div>
      </header>

      <h1 style={title} className="animate-rise">
        {run.topic}
      </h1>
      {run.from_cache && (
        <p style={cacheNote}>
          Ready instantly — reused from a similar topic studied earlier
          {run.cached_topic ? ` (“${run.cached_topic}”)` : ""}.
        </p>
      )}
      <p style={sub}>Your materials are ready. Open any one to read or watch it, or save it for later.</p>

      {materials.length === 0 ? (
        <p style={emptyNote}>
          This session finished, but no materials came back. Try studying the topic again.
        </p>
      ) : (
        <>
          <ul style={list}>
            {materials.map((m) => (
              <li key={m.key} style={row}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={mTitle}>{m.title}</div>
                  <div style={mBlurb}>{m.blurb}</div>
                </div>
                <div style={rowActions}>
                  <button onClick={() => setOpen(m)} style={openBtn}>
                    {m.kind === "video" ? "Watch" : "Read"}
                  </button>
                </div>
              </li>
            ))}
          </ul>

          <button onClick={() => run_id && downloadZip(run_id)} style={zipBtn}>
            Download everything (.zip)
          </button>
        </>
      )}

      {open && run_id && (
        <MaterialViewer run_id={run_id} material={open} onClose={() => setOpen(null)} />
      )}
    </main>
  );
}

function Centered({ children, tone }: { children: React.ReactNode; tone?: "flag" }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        padding: "80px 20px",
        color: tone === "flag" ? c.flag : c.inkSoft,
        fontFamily: font.mono,
        fontSize: size.body,
      }}
    >
      {children}
    </div>
  );
}

// ── styles ────────────────────────────────────────────────────────────────────

const headRight: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: space.base,
};

const benchLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: c.inkSoft,
};

const page: React.CSSProperties = { maxWidth: layout.shell, margin: "0 auto", padding: "34px 22px 90px" };

const headRow: React.CSSProperties = { display: "flex", alignItems: "baseline", gap: 10, marginBottom: 24 };
const backLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: c.inkSoft,
};

const title: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: display,
  fontWeight: 600,
  lineHeight: 1.02,
  letterSpacing: "-0.02em",
  color: c.ink,
};
const sub: React.CSSProperties = { fontSize: size.lead, color: c.inkSoft, marginTop: 12, maxWidth: 460 };
const cacheNote: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  color: c.reagent,
  marginTop: 10,
  letterSpacing: "0.01em",
};
const emptyNote: React.CSSProperties = { marginTop: 24, color: c.inkFaint, fontSize: size.body };

const list: React.CSSProperties = { listStyle: "none", marginTop: 34, borderTop: hairline };
const row: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 16,
  padding: "22px 2px",
  borderBottom: `1px solid ${c.rule}`,
};
const mTitle: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: size.head,
  fontWeight: 600,
  lineHeight: 1.05,
  color: c.ink,
};
const mBlurb: React.CSSProperties = { fontSize: size.body, color: c.inkSoft, marginTop: 4 };

const rowActions: React.CSSProperties = { flexShrink: 0 };
const openBtn: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  fontWeight: 700,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  border: `1px solid ${c.ink}`,
  backgroundColor: c.reagent,
  color: c.paper,
  padding: "11px 20px",
};

const zipBtn: React.CSSProperties = {
  marginTop: 32,
  width: "100%",
  border: `1px solid ${c.ink}`,
  backgroundColor: "transparent",
  color: c.ink,
  fontFamily: font.mono,
  fontSize: size.small,
  fontWeight: 700,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  padding: "15px 20px",
};
