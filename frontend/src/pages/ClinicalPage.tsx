import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  SERVER_UNAVAILABLE,
  type AgentInfo,
  type ClinicalSession,
  type ModelInfo,
  type ScoreResult,
} from "../api/client";
import {
  formatDuration,
  saveHistoryEntry,
  type StationHistoryEntry,
} from "../lib/clinicalHistory";

type Step = "model" | "cases" | "station" | "score";

type CaseCard = { id: string; title: string; stem: string; generated?: boolean };

const CASES_PER_PAGE = 5;

export default function ClinicalPage() {
  const [agent, setAgent] = useState<AgentInfo | null>(null);
  const [modelId, setModelId] = useState("med42-8b");
  const [step, setStep] = useState<Step>("model");
  const [cases, setCases] = useState<CaseCard[]>([]);
  const [casePage, setCasePage] = useState(0);
  const [session, setSession] = useState<ClinicalSession | null>(null);
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [timerRunning, setTimerRunning] = useState(false);
  const accumulatedMsRef = useRef(0);
  const segmentStartedRef = useRef<number | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  const selectedModel: ModelInfo | undefined = agent?.models.find((m) => m.id === modelId);

  function readElapsedSeconds() {
    let ms = accumulatedMsRef.current;
    if (segmentStartedRef.current != null) {
      ms += Date.now() - segmentStartedRef.current;
    }
    return Math.floor(ms / 1000);
  }

  function pauseTimer() {
    if (segmentStartedRef.current != null) {
      accumulatedMsRef.current += Date.now() - segmentStartedRef.current;
      segmentStartedRef.current = null;
    }
    setElapsed(Math.floor(accumulatedMsRef.current / 1000));
  }

  function resumeTimer() {
    if (segmentStartedRef.current == null) {
      segmentStartedRef.current = Date.now();
    }
  }

  function stopTimer() {
    pauseTimer();
    setTimerRunning(false);
  }

  function startTimer() {
    accumulatedMsRef.current = 0;
    segmentStartedRef.current = Date.now();
    setElapsed(0);
    setTimerRunning(true);
  }

  function resetTimer() {
    accumulatedMsRef.current = 0;
    segmentStartedRef.current = null;
    setElapsed(0);
    setTimerRunning(false);
  }

  useEffect(() => {
    api
      .agents()
      .then((res) => {
        const clinical = res.agents.find((a) => a.id === "clinical-station");
        if (clinical) {
          setAgent(clinical);
          setModelId(clinical.default_model);
        }
        setError(null);
      })
      .catch(() => setError(SERVER_UNAVAILABLE));
  }, []);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [session?.messages, busy]);

  // Run only while on station, not busy (examiner thinking pauses the clock)
  useEffect(() => {
    if (!timerRunning || step !== "station") return;

    if (busy) {
      pauseTimer();
      return;
    }

    resumeTimer();
    const id = window.setInterval(() => setElapsed(readElapsedSeconds()), 250);
    return () => window.clearInterval(id);
  }, [timerRunning, step, busy, session?.session_id]);

  async function loadCases() {
    const res = await api.clinicalCases();
    setCases(res.cases);
    setCasePage(0);
  }

  async function confirmModel() {
    setError(null);
    setBusy(true);
    try {
      await loadCases();
      setStep("cases");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cases");
    } finally {
      setBusy(false);
    }
  }

  async function generateCaseCard() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.generateClinicalCase(modelId);
      setCases((prev) => [res.case, ...prev.filter((c) => c.id !== res.case.id)]);
      setCasePage(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate case");
    } finally {
      setBusy(false);
    }
  }

  async function startWithCase(caseId: string) {
    setBusy(true);
    setError(null);
    setScore(null);
    try {
      const s = await api.startClinical(modelId, caseId);
      setSession(s);
      setStep("station");
      startTimer();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start");
      resetTimer();
    } finally {
      setBusy(false);
    }
  }

  async function send(message: string) {
    if (!session || !message.trim() || busy) return;
    setBusy(true);
    setError(null);
    setInput("");
    try {
      const s = await api.clinicalChat(session.session_id, message.trim());
      setSession(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    await send(input);
  }

  async function endAndScore() {
    if (!session) return;
    stopTimer();
    const durationSeconds = Math.floor(accumulatedMsRef.current / 1000);
    setElapsed(durationSeconds);
    setBusy(true);
    setError(null);
    try {
      const finalAnswer = input.trim() || undefined;
      if (finalAnswer) setInput("");
      const result = await api.clinicalScore(session.session_id, finalAnswer);
      setScore(result);
      setStep("score");
      const messagesForHistory = finalAnswer
        ? [...session.messages, { role: "user", content: finalAnswer }]
        : session.messages;
      const entry: StationHistoryEntry = {
        id: `${session.session_id}-${Date.now()}`,
        at: new Date().toISOString(),
        modelId: session.model_id,
        caseId: session.case.id,
        caseTitle: session.case.title,
        overallScore: result.overall_score,
        durationSeconds,
        passLikely: result.pass_likely,
        messages: messagesForHistory,
        score: result,
      };
      saveHistoryEntry(entry);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scoring failed");
    } finally {
      setBusy(false);
    }
  }

  function resetToCases() {
    setSession(null);
    setScore(null);
    setStep("cases");
    resetTimer();
  }

  function resetToModels() {
    setSession(null);
    setScore(null);
    setStep("model");
    resetTimer();
  }

  const diagnosis = score?.ideal_diagnosis || score?.case?.ideal_diagnosis;
  const casePageCount = Math.max(1, Math.ceil(cases.length / CASES_PER_PAGE));
  const safeCasePage = Math.min(casePage, casePageCount - 1);
  const pagedCases = cases.slice(
    safeCasePage * CASES_PER_PAGE,
    safeCasePage * CASES_PER_PAGE + CASES_PER_PAGE,
  );

  return (
    <div>
      <div className="section-head">
        <h2>Clinical Case Station</h2>
        <p>
          Pick a free Inference model, choose a clinical case card, use suggested question cards
          during the viva, then review diagnosis and a model 100/100 conversation.
        </p>
      </div>

      <div className="cases-toolbar" style={{ marginBottom: "0.75rem" }}>
        <div className="stepper" style={{ margin: 0, flex: 1 }}>
          <span className={`step-pill ${step === "model" ? "active" : ""}`}>1 · Model</span>
          <span className={`step-pill ${step === "cases" ? "active" : ""}`}>2 · Case cards</span>
          <span className={`step-pill ${step === "station" ? "active" : ""}`}>3 · Station</span>
          <span className={`step-pill ${step === "score" ? "active" : ""}`}>4 · Score</span>
        </div>
      </div>

      {step === "model" && !agent && (
        <div className="panel">
          {error ? (
            <div className="error-banner">{error}</div>
          ) : (
            <p className="muted">Connecting to server…</p>
          )}
        </div>
      )}

      {step === "model" && agent && selectedModel && (
        <div className="panel">
          <div className="model-detail-card">
            <div className="badges">
              <span className="badge rec">Free</span>
              <span className="badge rec">Selected for CST</span>
              <span className="badge">{selectedModel.size}</span>
            </div>
            <h3>{selectedModel.name}</h3>
            <p className="muted mono">{selectedModel.huggingface_id}</p>
            <p className="model-detail-body">{selectedModel.description}</p>
            <h4>Trained on</h4>
            <ul className="strength-list">
              {(selectedModel.training_datasets ?? []).map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
            <h4>Strengths</h4>
            <ul className="strength-list">
              {selectedModel.strengths.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            <button className="btn btn-primary" type="button" onClick={confirmModel} disabled={busy}>
              {busy ? "Loading cases…" : "Continue to case cards"}
            </button>
          </div>
          {error && <div className="error-banner">{error}</div>}
        </div>
      )}

      {step === "cases" && (
        <div className="panel">
          <div className="cases-toolbar">
            <div>
              <h3 style={{ margin: 0, fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>
                Case cards
              </h3>
              <p className="muted" style={{ margin: "0.25rem 0 0" }}>
                Model: <strong>{selectedModel?.name}</strong> · {cases.length} cards — pick one,
                random, or generate a new card.
              </p>
            </div>
            <div className="cta-row">
              <button className="btn btn-ghost" type="button" onClick={resetToModels}>
                Change model
              </button>
              <button
                className="btn btn-ghost"
                type="button"
                disabled={busy || cases.length === 0}
                onClick={() => {
                  const pick = cases[Math.floor(Math.random() * cases.length)];
                  if (pick) void startWithCase(pick.id);
                }}
              >
                Random
              </button>
              <button className="btn btn-primary" type="button" onClick={generateCaseCard} disabled={busy}>
                {busy ? "Generating…" : "Generate new card"}
              </button>
            </div>
          </div>

          <div className="case-card-grid">
            {pagedCases.map((c) => (
              <button
                key={c.id}
                type="button"
                className="case-card"
                disabled={busy}
                onClick={() => startWithCase(c.id)}
              >
                <div className="badges">
                  {c.generated && <span className="badge rec">Generated</span>}
                  <span className="badge">CST</span>
                </div>
                <h4>{c.title}</h4>
                <p>{c.stem}</p>
                <span className="case-card-cta">Start this station →</span>
              </button>
            ))}
          </div>

          <div className="cases-pagination">
            <button
              className="btn btn-ghost"
              type="button"
              disabled={busy || safeCasePage <= 0}
              onClick={() => setCasePage((p) => Math.max(0, p - 1))}
            >
              Previous
            </button>
            <span className="muted">
              Page {safeCasePage + 1} of {casePageCount}
            </span>
            <button
              className="btn btn-ghost"
              type="button"
              disabled={busy || safeCasePage >= casePageCount - 1}
              onClick={() => setCasePage((p) => Math.min(casePageCount - 1, p + 1))}
            >
              Next
            </button>
          </div>
          {error && <div className="error-banner">{error}</div>}
        </div>
      )}

      {step === "station" && session && (
        <div className="panel">
          <div className="station-top">
            <div>
              <div className="eyebrow" style={{ color: "var(--mint)", fontWeight: 600 }}>
                Phase · {session.phase}
              </div>
              <h3 style={{ margin: "0.2rem 0", fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>
                {session.case.title}
              </h3>
            </div>
            <div className="timer-block" aria-live="polite">
              <span className="timer-label">{busy ? "Paused" : "Elapsed"}</span>
              <strong className="timer-value">{formatDuration(elapsed)}</strong>
            </div>
            <div className="cta-row">
              <button className="btn btn-danger" type="button" onClick={endAndScore} disabled={busy}>
                End & score
              </button>
              <button className="btn btn-ghost" type="button" onClick={resetToCases}>
                Back to cards
              </button>
            </div>
          </div>

          <div className="chat-layout">
            <div>
              <div className="chat-thread station-thread" ref={threadRef}>
                {session.messages.map((m, i) => (
                  <div key={`${m.role}-${i}`} className={`bubble ${m.role}`}>
                    {m.content}
                  </div>
                ))}
                {busy && <div className="bubble assistant loading-dot">Examiner thinking</div>}
              </div>
              <form className="composer" onSubmit={onSubmit}>
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a history / examination question, or state diagnosis & plan…"
                  disabled={busy}
                />
                <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>
                  Send
                </button>
              </form>
              {error && <div className="error-banner">{error}</div>}
            </div>

            <aside className="question-cards" key={session.suggested_questions.join("|")}>
              <h4>Suggested questions</h4>
              <p className="question-cards-hint">
                After each pick, new cards appear to dig deeper toward diagnosis &amp; plan
                {session.phase ? ` · ${session.phase}` : ""}
              </p>
              {session.suggested_questions.map((q, i) => (
                <button
                  key={`${i}-${q}`}
                  type="button"
                  className="q-card"
                  disabled={busy}
                  onClick={() => send(q)}
                >
                  {q}
                </button>
              ))}
            </aside>
          </div>
        </div>
      )}

      {step === "score" && score && (
        <div className="panel">
          <div className="station-top">
            <div className="section-head" style={{ margin: 0 }}>
              <h2 style={{ margin: 0 }}>
                Score · {score.overall_score}/100{" "}
                <span className="muted" style={{ fontSize: "1rem" }}>
                  {score.pass_likely ? "Likely pass" : "Needs work"}
                </span>
              </h2>
              <p style={{ margin: "0.35rem 0 0" }}>{score.ideal_summary}</p>
            </div>
            <div className="timer-block">
              <span className="timer-label">Time to score</span>
              <strong className="timer-value">{formatDuration(elapsed)}</strong>
            </div>
          </div>

          <div className="diagnosis-banner">
            <span className="timer-label">True diagnosis</span>
            <strong>{diagnosis}</strong>
            {score.case?.key_features && (
              <p className="muted" style={{ margin: "0.45rem 0 0" }}>
                Key features: {score.case.key_features.join(" · ")}
              </p>
            )}
          </div>

          <div className="diagnosis-banner diagnosis-assess">
            <span className="timer-label">Your diagnosis assessment</span>
            <strong>
              {score.diagnosis_stated
                ? score.candidate_diagnosis || "Stated (see transcript)"
                : "Not stated"}
            </strong>
            <p className="muted" style={{ margin: "0.45rem 0 0" }}>
              Proximity: {(score.diagnosis_proximity || "unknown").replaceAll("_", " ")}
              {typeof score.questions_to_correct === "number"
                ? ` · ~${score.questions_to_correct} question(s) from correct`
                : ""}
              {score.scoring_backend ? ` · scored via ${score.scoring_backend}` : ""}
            </p>
          </div>

          <div className="score-grid">
            {Object.entries(score.subscores ?? {}).map(([k, v]) => (
              <div key={k} className="score-tile">
                <strong>{v}</strong>
                <span>{k.replaceAll("_", " ")}</span>
              </div>
            ))}
          </div>

          <h3 style={{ fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>What went well</h3>
          <ul>
            {(score.what_went_well ?? []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>

          <h3 style={{ fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>Gaps</h3>
          <ul>
            {(score.gaps ?? []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>

          <h3 style={{ fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>Better answers</h3>
          {(score.better_answers ?? []).map((ba) => (
            <div key={`${ba.topic}-${ba.stronger_answer}`} className="better-answer">
              <strong>{ba.topic}</strong>
              <p className="muted">You: {ba.candidate_said}</p>
              <p>
                <strong>Stronger:</strong> {ba.stronger_answer}
              </p>
              <p className="muted">{ba.why}</p>
            </div>
          ))}

          <h3 style={{ fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>
            Model conversation for ~100/100
          </h3>
          <p className="muted">
            Example viva showing how a strong candidate reaches the diagnosis and management.
          </p>
          <div className="model-conversation">
            {(score.model_conversation ?? []).map((m, i) => (
              <div key={`model-${i}`} className={`bubble ${m.role}`}>
                {m.content}
              </div>
            ))}
          </div>

          <div className="cta-row" style={{ marginTop: "1rem" }}>
            <button className="btn btn-primary" type="button" onClick={resetToCases}>
              Another case card
            </button>
            <button className="btn btn-ghost" type="button" onClick={resetToModels}>
              Change model
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
