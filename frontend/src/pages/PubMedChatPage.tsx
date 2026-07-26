import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, SERVER_UNAVAILABLE, type AgentInfo, type PubMedChatSession } from "../api/client";
import ModelPicker from "../components/ModelPicker";

export default function PubMedChatPage() {
  const [agent, setAgent] = useState<AgentInfo | null>(null);
  const [modelId, setModelId] = useState("pmc-llama-summ");
  const [session, setSession] = useState<PubMedChatSession | null>(null);
  const [input, setInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .agents()
      .then((res) => {
        const chat = res.agents.find((a) => a.id === "pubmed-chat");
        if (chat) {
          setAgent(chat);
          setModelId(chat.default_model);
        }
        setError(null);
      })
      .catch(() => setError(SERVER_UNAVAILABLE));
  }, []);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [session?.messages, busy]);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const s = await api.startPubMedChat(modelId);
      setSession(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!session || !input.trim()) return;
    setBusy(true);
    setError(null);
    const message = input.trim();
    setInput("");
    try {
      const s = await api.pubmedChat(
        session.session_id,
        message,
        searchQuery.trim() || undefined,
      );
      setSession(s);
      setSearchQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="section-head">
        <h2>PubMed Literature Chat</h2>
        <p>
          Search live PubMed, summarise abstracts, compare papers, or draft grounded content with a
          biomedical generative model.
        </p>
      </div>

      {!session && (
        <div className="panel">
          {agent && <ModelPicker models={agent.models} selected={modelId} onSelect={setModelId} />}
          <button className="btn btn-primary" type="button" onClick={start} disabled={busy}>
            {busy ? "Starting…" : "Start literature chat"}
          </button>
          {error && <div className="error-banner">{error}</div>}
        </div>
      )}

      {session && (
        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
            <p className="muted" style={{ margin: 0 }}>
              Model: <strong>{session.model_id}</strong>
            </p>
            <button className="btn btn-ghost" type="button" onClick={() => setSession(null)}>
              Change model
            </button>
          </div>

          <div className="chat-layout" style={{ marginTop: "1rem" }}>
            <div>
              <div className="chat-thread" ref={threadRef}>
                {session.messages.map((m, i) => (
                  <div key={`${m.role}-${i}`} className={`bubble ${m.role}`}>
                    {m.content}
                  </div>
                ))}
                {busy && <div className="bubble assistant loading-dot">Thinking</div>}
              </div>
              <form className="composer" onSubmit={onSubmit}>
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  <input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Optional PubMed search query (e.g. anastomotic leak risk factors)"
                    style={{
                      borderRadius: 12,
                      border: "1px solid var(--line)",
                      padding: "0.55rem 0.8rem",
                      background: "rgba(255,255,255,0.85)",
                    }}
                    disabled={busy}
                  />
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask to summarise, compare, explain, or draft…"
                    disabled={busy}
                  />
                  <div className="cta-row" style={{ margin: 0, flexWrap: "wrap" }}>
                    {[
                      "What is PubMed in one sentence?",
                      "Summarise recent papers on acute appendicitis",
                      "Compare open vs laparoscopic appendectomy evidence",
                    ].map((q) => (
                      <button
                        key={q}
                        type="button"
                        className="btn btn-ghost"
                        disabled={busy}
                        style={{ fontSize: "0.85rem" }}
                        onClick={async () => {
                          if (!session || busy) return;
                          setBusy(true);
                          setError(null);
                          setInput("");
                          try {
                            const s = await api.pubmedChat(
                              session.session_id,
                              q,
                              searchQuery.trim() || undefined,
                            );
                            setSession(s);
                            setSearchQuery("");
                          } catch (err) {
                            setError(err instanceof Error ? err.message : "Chat failed");
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
                <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>
                  Send
                </button>
              </form>
              {error && <div className="error-banner">{error}</div>}
            </div>

            <aside className="question-cards">
              <h4>Retrieved papers</h4>
              {(session.last_articles ?? []).length === 0 && (
                <p className="muted">Run a search or ask about a topic to load abstracts.</p>
              )}
              {(session.last_articles ?? []).map((a) => (
                <a
                  key={a.pmid}
                  className="q-card"
                  href={a.pubmed_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ display: "block" }}
                >
                  <strong>PMID {a.pmid}</strong>
                  <div>{a.title}</div>
                </a>
              ))}
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
