import { useEffect, useState, type FormEvent } from "react";
import { api, type AgentInfo, type MatchResult } from "../api/client";
import ModelPicker from "../components/ModelPicker";

export default function MatcherPage() {
  const [agent, setAgent] = useState<AgentInfo | null>(null);
  const [modelId, setModelId] = useState("pubmedbert-embeddings");
  const [text, setText] = useState("");
  const [result, setResult] = useState<MatchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.agents().then((res) => {
      const matcher = res.agents.find((a) => a.id === "pubmed-matcher");
      if (matcher) {
        setAgent(matcher);
        setModelId(matcher.default_model);
      }
    });
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (text.trim().length < 20) {
      setError("Paste at least ~20 characters of text to match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.matchText(text.trim(), modelId);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Match failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="section-head">
        <h2>PubMed Article Matcher</h2>
        <p>
          Embed your fragment with NeuML PubMedBERT embeddings and rank the closest articles by
          cosine similarity. High confidence returns an exact article match.
        </p>
      </div>

      <div className="panel">
        {agent && <ModelPicker models={agent.models} selected={modelId} onSelect={setModelId} />}

        <form onSubmit={onSubmit}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste a paragraph, abstract excerpt, or clinical text snippet…"
            style={{
              width: "100%",
              minHeight: 160,
              borderRadius: 14,
              border: "1px solid var(--line)",
              padding: "0.85rem 1rem",
              background: "rgba(255,255,255,0.85)",
            }}
          />
          <div className="cta-row" style={{ marginTop: "0.85rem" }}>
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "Matching…" : "Find articles"}
            </button>
          </div>
        </form>
        {error && <div className="error-banner">{error}</div>}
      </div>

      {result && (
        <div className="panel" style={{ marginTop: "1rem" }}>
          {result.exact_match && result.exact_article ? (
            <div className="match-item exact">
              <div className="badges">
                <span className="badge rec">Exact match</span>
                <span className="badge">score {result.exact_article.score}</span>
              </div>
              <h3 style={{ fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>
                {result.exact_article.title}
              </h3>
              <p className="muted">
                PMID {result.exact_article.pmid} · {result.exact_article.journal} ·{" "}
                {result.exact_article.year}
              </p>
              <p>{result.exact_article.abstract}</p>
              <a href={result.exact_article.pubmed_url} target="_blank" rel="noreferrer">
                Open on PubMed →
              </a>
            </div>
          ) : (
            <p className="muted">
              No exact match above threshold ({result.threshold}). Showing top {result.top_matches.length}{" "}
              from a corpus of {result.corpus_size} articles.
            </p>
          )}

          <h3 style={{ fontFamily: "var(--font-display)", color: "var(--teal-deep)" }}>Top 3</h3>
          <div className="match-result">
            {result.top_matches.map((article, idx) => (
              <div key={article.pmid} className="match-item">
                <div className="badges">
                  <span className="badge">#{idx + 1}</span>
                  <span className="badge">similarity {article.score}</span>
                </div>
                <h4 style={{ marginBottom: 0 }}>{article.title}</h4>
                <p className="muted">
                  PMID {article.pmid} · {article.journal} · {article.year}
                </p>
                <p>{article.abstract}</p>
                <a href={article.pubmed_url} target="_blank" rel="noreferrer">
                  Open on PubMed →
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
