import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import ScoreChart from "../components/ScoreChart";
import { formatDuration, loadHistory } from "../lib/clinicalHistory";

export default function ClinicalProgressPage() {
  const [history] = useState(() => loadHistory());
  const [openId, setOpenId] = useState<string | null>(null);

  const chartPoints = useMemo(
    () =>
      [...history]
        .reverse()
        .map((h, i) => ({
          label: `#${i + 1}`,
          score: h.overallScore,
        })),
    [history],
  );

  return (
    <div>
      <div className="section-head">
        <h2>CST progress</h2>
        <p>Score progression and past station chats — separate from the live viva.</p>
      </div>

      <div className="stepper">
        <Link className="step-pill step-link" to="/clinical">
          1 · Model
        </Link>
        <Link className="step-pill step-link" to="/clinical">
          2 · Case cards
        </Link>
        <Link className="step-pill step-link" to="/clinical">
          3 · Station
        </Link>
        <Link className="step-pill step-link" to="/clinical">
          4 · Score
        </Link>
      </div>

      <div className="cta-row" style={{ marginBottom: "1rem" }}>
        <Link className="btn btn-primary" to="/clinical">
          Back to CST station
        </Link>
      </div>

      <section className="panel">
        <div className="section-head">
          <h2>Score progression</h2>
          <p>How your overall station scores have changed over attempts.</p>
        </div>
        <ScoreChart points={chartPoints} />
      </section>

      <section className="panel history-panel">
        <h3 style={{ fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>Past stations</h3>
        {history.length === 0 && <p className="muted">No scored stations yet.</p>}
        <div className="history-list">
          {history.map((h) => (
            <div key={h.id} className="history-item">
              <button
                type="button"
                className="history-summary"
                onClick={() => setOpenId(openId === h.id ? null : h.id)}
              >
                <div>
                  <strong>
                    {h.overallScore}/100 · {h.caseTitle}
                  </strong>
                  <div className="muted">
                    {new Date(h.at).toLocaleString()} · {formatDuration(h.durationSeconds)} ·{" "}
                    {h.modelId} · {h.passLikely ? "pass" : "needs work"}
                  </div>
                </div>
                <span className="muted">{openId === h.id ? "Hide" : "Chat"}</span>
              </button>
              {openId === h.id && (
                <div className="history-chat">
                  {h.score?.ideal_diagnosis && (
                    <p className="muted">
                      Diagnosis: <strong>{h.score.ideal_diagnosis}</strong>
                    </p>
                  )}
                  {h.messages.map((m, i) => (
                    <div key={`${h.id}-${i}`} className={`bubble ${m.role}`}>
                      {m.content}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
