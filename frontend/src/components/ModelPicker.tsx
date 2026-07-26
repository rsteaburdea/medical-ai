import type { ModelInfo } from "../api/client";

interface Props {
  models: ModelInfo[];
  selected: string;
  onSelect: (id: string) => void;
}

export default function ModelPicker({ models, selected, onSelect }: Props) {
  return (
    <div className="model-grid">
      {models.map((m) => (
        <button
          key={m.id}
          type="button"
          className={`model-option ${selected === m.id ? "selected" : ""}`}
          onClick={() => onSelect(m.id)}
        >
          <h4>{m.name}</h4>
          <p>{m.description}</p>
          {(m.training_datasets?.length ?? 0) > 0 && (
            <p className="muted" style={{ fontSize: "0.82rem", marginTop: "0.35rem" }}>
              Trained on: {m.training_datasets!.slice(0, 2).join(" · ")}
              {m.training_datasets!.length > 2 ? "…" : ""}
            </p>
          )}
          <div className="badges">
            <span className="badge">{m.size}</span>
            <span className="badge rec">Free</span>
            {m.recommended && <span className="badge rec">Recommended</span>}
            {m.multimodal && <span className="badge">Multimodal</span>}
          </div>
        </button>
      ))}
    </div>
  );
}
