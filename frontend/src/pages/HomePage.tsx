import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, SERVER_UNAVAILABLE, type AgentInfo } from "../api/client";

const ROUTES: Record<string, string> = {
  "clinical-station": "/clinical",
  "pubmed-matcher": "/matcher",
  "pubmed-chat": "/pubmed-chat",
};

export default function HomePage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [hfOk, setHfOk] = useState<boolean | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [serverDown, setServerDown] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.agents(), api.health()])
      .then(([agentsRes, health]) => {
        if (cancelled) return;
        setAgents(agentsRes.agents);
        setHfOk(health.hf_token_configured);
        setDemoMode(Boolean(health.demo_mode));
        setServerDown(false);
        setError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setAgents([]);
        setServerDown(true);
        setError(SERVER_UNAVAILABLE);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <div className="brand" style={{ marginBottom: "1rem" }}>
            <strong style={{ fontSize: "clamp(2.8rem, 6vw, 4.6rem)" }}>MedTrain AI</strong>
          </div>
          <h1>Train like the station. Ground answers in literature.</h1>
          <p>
            Pick a Hugging Face medical model, then run an Irish CST-style clinical viva, match
            unknown text to PubMed papers, or talk through the biomedical literature — shareable
            with anyone who has the link.
          </p>
          <div className="cta-row">
            <Link className="btn btn-primary" to="/clinical">
              Start CST station
            </Link>
            <Link className="btn btn-ghost" to="/matcher">
              Match a PubMed fragment
            </Link>
          </div>
          {demoMode && (
            <p className="muted" style={{ marginTop: "1rem" }}>
              Running in demo mode (offline clinical examiner + TF-IDF matcher). Add{" "}
              <code>HF_TOKEN</code> in <code>backend/.env</code> for live Hugging Face models.
            </p>
          )}
          {hfOk === false && !demoMode && (
            <p className="muted" style={{ marginTop: "1rem" }}>
              HF_TOKEN is not configured on the server — add it in <code>backend/.env</code> to call
              Hugging Face models.
            </p>
          )}
          {(serverDown || error) && <div className="error-banner">{error ?? SERVER_UNAVAILABLE}</div>}
        </div>
        <div className="hero-visual" aria-hidden>
          <div className="pulse" />
          <div className="pulse" />
        </div>
      </section>

      <section>
        <div className="section-head">
          <h2>Choose an agent</h2>
          <p>Each agent exposes the models best suited to its job. Select one to continue.</p>
        </div>
        {loading && <p className="muted">Connecting to server…</p>}
        {!loading && serverDown && (
          <div className="error-banner">{SERVER_UNAVAILABLE}</div>
        )}
        {!loading && !serverDown && agents.length === 0 && (
          <p className="muted">No agents returned by the server yet.</p>
        )}
        <div className="agent-grid">
          {agents.map((agent, i) => (
            <Link
              key={agent.id}
              to={ROUTES[agent.id] ?? "/"}
              className="agent-card"
              style={{ animationDelay: `${0.08 * i}s` }}
            >
              <div className="eyebrow">{agent.category.replace("_", " ")}</div>
              <h3>{agent.name}</h3>
              <p>{agent.tagline}</p>
              <span className="muted">{agent.models.length} models available →</span>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
