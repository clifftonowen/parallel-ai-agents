import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { downloadFile, downloadZip, fetchFileText, fileUrl, getRun } from "../api/client";
import Markdown from "../components/Markdown";
import { parseFlashcards } from "../lib/flashcards";
import { useRunGrant } from "../hooks/useRunGrant";
import { DEMO } from "../api/demo";
import { hasBenchmarkData } from "../types";
import type { OutputPaths, RunState } from "../types";
import {
  c, display, font, headingWeight, layout, muted, mutedFaint, size, space,
} from "../theme";

const basename = (p: string) => p.split(/[\\/]/).pop() ?? p;

type Tab = "notes" | "flashcards" | "video" | "pdf";

function DocTab({ run_id, filename }: { run_id: string; filename: string }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(null);
    setError(null);
    fetchFileText(run_id, filename)
      .then(setText)
      .catch(() => setError("Couldn't load that file."));
  }, [run_id, filename]);

  if (error) return <p style={{ color: c.flagDeep }}>{error}</p>;
  if (text === null) return <p style={{ color: muted }}>Loading…</p>;
  return (
    <div style={{ maxWidth: layout.measure }}>
      <Markdown source={text} />
    </div>
  );
}

function FlashcardsTab({ run_id, filename }: { run_id: string; filename: string }) {
  const [text, setText] = useState<string | null>(null);
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});

  useEffect(() => {
    fetchFileText(run_id, filename).then(setText).catch(() => setText(""));
  }, [run_id, filename]);

  const cards = useMemo(() => (text ? parseFlashcards(text) : []), [text]);

  if (text === null) return <p style={{ color: muted }}>Loading…</p>;
  if (cards.length === 0) {
    return <DocTab run_id={run_id} filename={filename} />;
  }

  return (
    <>
      <p style={hint}>Click a card to turn it over.</p>
      <div style={cardGrid}>
        {cards.map((card, i) => {
          const isBack = !!flipped[i];
          return (
            <button
              key={i}
              className="card elev-sm card-link"
              aria-expanded={isBack}
              onClick={() => setFlipped((f) => ({ ...f, [i]: !f[i] }))}
              style={{
                ...flipCard,
                background: isBack ? c.reagentWash : c.paperCard,
              }}
            >
              <span className="card-kicker">{isBack ? "Answer" : "Question"}</span>
              <span style={isBack ? cardAnswer : cardQuestion}>{isBack ? card.a : card.q}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}

export default function PackagePage() {
  const { run_id } = useParams<{ run_id?: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunState | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("notes");
  const grant = useRunGrant(run_id);

  useEffect(() => {
    if (!run_id) return;
    getRun(run_id)
      .then(setRun)
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Couldn't load your materials.")
      )
      .finally(() => setLoading(false));
  }, [run_id]);

  const outputs: OutputPaths = useMemo(() => run?.outputs ?? {}, [run]);
  const tabs = useMemo(() => {
    const t: { key: Tab; label: string }[] = [];
    if (outputs.notes_md) t.push({ key: "notes", label: "Notes" });
    if (outputs.flashcards_md) t.push({ key: "flashcards", label: "Flashcards" });
    if (outputs.video) t.push({ key: "video", label: "Video" });
    if (outputs.notes_pdf || outputs.flashcards_pdf) t.push({ key: "pdf", label: "PDF" });
    return t;
  }, [outputs]);

  useEffect(() => {
    if (tabs.length && !tabs.some((t) => t.key === tab)) setTab(tabs[0].key);
  }, [tabs, tab]);

  if (loading) return <p style={{ color: muted }}>Opening your study materials…</p>;
  if (err || !run) return <p style={{ color: c.flagDeep }}>{err ?? "Nothing to show here."}</p>;

  const pdfs = [
    outputs.notes_pdf && { label: "Notes", filename: basename(outputs.notes_pdf) },
    outputs.flashcards_pdf && {
      label: "Flashcards",
      filename: basename(outputs.flashcards_pdf),
    },
  ].filter(Boolean) as { label: string; filename: string }[];

  return (
    <main style={page}>
      <div style={head}>
        <div style={{ minWidth: 0 }}>
          <span style={kicker}>Session</span>
          <h1 style={heading}>{run.topic}</h1>
          <div style={metaRow}>
            <span className="tag tag-outline">{run.mode ?? "async"}</span>
            {hasBenchmarkData(run.benchmark) && (
              <Link to={`/benchmark/${run.run_id}`} style={metaLink}>
                timings and tokens →
              </Link>
            )}
          </div>
        </div>
        {!DEMO && (
          <button className="btn btn-secondary" onClick={() => downloadZip(run.run_id)}>
            Download all (.zip)
          </button>
        )}
      </div>

      {run.from_cache && (
        <p style={cacheNote}>
          Ready instantly — reused from a similar topic studied earlier
          {run.cached_topic ? ` (“${run.cached_topic}”)` : ""}.
        </p>
      )}

      {tabs.length === 0 ? (
        <p style={{ color: muted }}>
          This session finished, but no materials came back. Try the topic again.
        </p>
      ) : (
        <>
          <div className="seg" role="tablist" style={{ marginBottom: space.xl }}>
            {tabs.map((t) => (
              <button
                key={t.key}
                role="tab"
                className="seg-opt"
                aria-pressed={tab === t.key}
                aria-selected={tab === t.key}
                onClick={() => setTab(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === "notes" && outputs.notes_md && (
            <DocTab run_id={run.run_id} filename={basename(outputs.notes_md)} />
          )}

          {tab === "flashcards" && outputs.flashcards_md && (
            <FlashcardsTab run_id={run.run_id} filename={basename(outputs.flashcards_md)} />
          )}

          {tab === "video" && outputs.video && (
            <div style={{ maxWidth: 720 }}>
              <video
                controls
                // The grant, not the session token. A <video> re-requests this
                // URL on every seek, which is why the grant outlasts the page.
                src={fileUrl(run.run_id, basename(outputs.video), grant)}
                style={{ width: "100%", background: c.ink }}
              />
              <p style={hint}>A short narrated walkthrough with slides.</p>
            </div>
          )}

          {tab === "pdf" && (
            <div style={pdfRow}>
              {pdfs.map((p) => (
                <div key={p.filename} className="card elev-sm" style={{ width: 240 }}>
                  <div className="card-kicker">Print</div>
                  <div className="card-title">{p.label}</div>
                  <p className="card-body">Generated from the markdown via pandoc.</p>
                  <button
                    className="btn btn-primary"
                    onClick={() => downloadFile(run.run_id, p.filename)}
                  >
                    Download PDF
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <button className="btn btn-ghost" style={{ marginTop: space.section }} onClick={() => navigate("/new")}>
        ← Start another session
      </button>
    </main>
  );
}

// ── styles ──────────────────────────────────────────────────────────────────

const page: React.CSSProperties = { maxWidth: layout.shell };

const head: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: space.base,
  marginBottom: space.lg,
  flexWrap: "wrap",
};

const kicker: React.CSSProperties = {
  display: "block",
  fontSize: size.small,
  fontStyle: "italic",
  color: c.reagentDeep,
  marginBottom: space.xs,
};

const heading: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: display,
  lineHeight: 1.05,
  margin: `0 0 ${space.sm}px`,
};

const metaRow: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: space.md,
  flexWrap: "wrap",
};

const metaLink: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
};

const cacheNote: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
  color: mutedFaint,
  marginBottom: space.base,
};

const hint: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
  color: mutedFaint,
  margin: `${space.md}px 0`,
};

const cardGrid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
  gap: space.base,
  alignItems: "start",
};

const flipCard: React.CSSProperties = {
  cursor: "pointer",
  textAlign: "left",
  minHeight: 140,
  transition: "background-color 0.15s, box-shadow 0.15s",
};

const cardQuestion: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.lead,
  lineHeight: 1.3,
};

const cardAnswer: React.CSSProperties = {
  fontSize: size.body,
  lineHeight: 1.5,
  color: c.ink,
};

const pdfRow: React.CSSProperties = {
  display: "flex",
  gap: space.base,
  flexWrap: "wrap",
};
