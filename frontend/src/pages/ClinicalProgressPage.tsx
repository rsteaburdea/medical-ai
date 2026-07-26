import { useMemo, useState } from "react";
import ScoreChart from "../components/ScoreChart";
import {
  clearScoreProgression,
  clearStationChats,
  dailyAveragePoints,
  formatDuration,
  lastWeekAverage,
  loadHistory,
  loadScoreProgress,
  todayAverage,
  type ScoreProgressEntry,
  type StationHistoryEntry,
} from "../lib/clinicalHistory";

const STATIONS_PER_PAGE = 5;

export default function ClinicalProgressPage() {
  const [history, setHistory] = useState<StationHistoryEntry[]>(() => loadHistory());
  const [scores, setScores] = useState<ScoreProgressEntry[]>(() => loadScoreProgress());
  const [openId, setOpenId] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const chartPoints = useMemo(() => dailyAveragePoints(scores), [scores]);
  const weekAvg = useMemo(() => lastWeekAverage(scores), [scores]);
  const dayAvg = useMemo(() => todayAverage(scores), [scores]);

  const pageCount = Math.max(1, Math.ceil(history.length / STATIONS_PER_PAGE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedHistory = history.slice(
    safePage * STATIONS_PER_PAGE,
    safePage * STATIONS_PER_PAGE + STATIONS_PER_PAGE,
  );

  function clearProgression() {
    if (!window.confirm("Clear score progression chart and averages? Past station chats are kept.")) {
      return;
    }
    clearScoreProgression();
    setScores([]);
  }

  function clearChats() {
    if (!window.confirm("Clear all past station chats? Score progression is kept.")) {
      return;
    }
    clearStationChats();
    setHistory([]);
    setOpenId(null);
    setPage(0);
  }

  return (
    <div>
      <div className="section-head">
        <h2>CST progress</h2>
        <p>Score progression and past station chats — separate from the live viva.</p>
      </div>

      <section className="panel">
        <div className="section-head section-head-row">
          <div>
            <h2>Score progression</h2>
            <p>Daily average score (each point = mean of that day&apos;s stations). Hover a point for the value.</p>
          </div>
          <button
            className="btn btn-ghost"
            type="button"
            disabled={scores.length === 0}
            onClick={clearProgression}
          >
            Clear all
          </button>
        </div>
        <div className="progress-stats">
          <div className="progress-stat">
            <span className="timer-label">Today&apos;s average</span>
            <strong>{dayAvg == null ? "—" : `${dayAvg}/100`}</strong>
          </div>
          <div className="progress-stat">
            <span className="timer-label">Last 7 days average</span>
            <strong>{weekAvg == null ? "—" : `${weekAvg}/100`}</strong>
          </div>
        </div>
        <ScoreChart points={chartPoints} />
      </section>

      <section className="panel history-panel">
        <div className="section-head section-head-row" style={{ marginBottom: "0.5rem" }}>
          <h3 style={{ fontFamily: "var(--font-display)", color: "var(--teal-deep)", margin: 0 }}>
            Past stations
          </h3>
          <button
            className="btn btn-ghost"
            type="button"
            disabled={history.length === 0}
            onClick={clearChats}
          >
            Clear all
          </button>
        </div>
        {history.length === 0 && <p className="muted">No scored stations yet.</p>}
        {history.length > 0 && (
          <p className="muted" style={{ marginTop: 0 }}>
            Showing {pagedHistory.length} of {history.length} · 5 per page
          </p>
        )}
        <div className="history-list">
          {pagedHistory.map((h) => (
            <div key={h.id} className="history-item">
              <button
                type="button"
                className="history-summary"
                onClick={() => setOpenId(openId === h.id ? null : h.id)}
              >
                <div>
                  <strong className="history-case-title">{h.caseTitle}</strong>
                  <div className="muted">
                    {h.overallScore}/100 · {new Date(h.at).toLocaleString()} ·{" "}
                    {formatDuration(h.durationSeconds)} · {h.modelId} ·{" "}
                    {h.passLikely ? "pass" : "needs work"}
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
        {history.length > STATIONS_PER_PAGE && (
          <div className="cases-pagination">
            <button
              className="btn btn-ghost"
              type="button"
              disabled={safePage <= 0}
              onClick={() => {
                setOpenId(null);
                setPage((p) => Math.max(0, p - 1));
              }}
            >
              Previous
            </button>
            <span className="muted">
              Page {safePage + 1} of {pageCount}
            </span>
            <button
              className="btn btn-ghost"
              type="button"
              disabled={safePage >= pageCount - 1}
              onClick={() => {
                setOpenId(null);
                setPage((p) => Math.min(pageCount - 1, p + 1));
              }}
            >
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
