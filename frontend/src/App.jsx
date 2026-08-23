import React, { useEffect, useState, useCallback } from "react";
import { api } from "./api";

const KIND_OPTIONS = [
  { value: "w2", label: "W-2" },
  { value: "prior_year_1040", label: "Prior-year 1040" },
  { value: "government_id", label: "Government ID" },
];

const REASON_LABEL = {
  low_confidence: "Low confidence",
  unreadable: "Could not read the scan",
  wrong_year: "Wrong tax year",
  unknown_person: "Person not on this return",
  no_matching_slot: "No open slot for this",
};

export default function App() {
  const [clientId, setClientId] = useState(null);
  const [status, setStatus] = useState(null);
  const [people, setPeople] = useState([]);
  const [facts, setFacts] = useState([]);
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const refresh = useCallback(async (id) => {
    const [st, pl, fa, rn] = await Promise.all([
      api.status(id),
      api.people(id),
      api.facts(id),
      api.runs(id),
    ]);
    setStatus(st);
    setPeople(pl);
    setFacts(fa);
    setRuns(rn);
  }, []);

  useEffect(() => {
    api.clients().then((cs) => {
      if (cs.length) {
        setClientId(cs[0].id);
        refresh(cs[0].id);
      }
    });
  }, [refresh]);

  const flash = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const withBusy = async (fn, msg) => {
    setBusy(true);
    try {
      await fn();
      await refresh(clientId);
      if (msg) flash(msg);
    } catch (e) {
      flash("Error: " + e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!status) return <div className="loading">Loading…</div>;

  const c = status.client;
  const s = status.summary;

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>{c.name}</h1>
          <div className="sub">
            Tax year {c.tax_year} · {c.filing_status.replace("_", " ")} · derivation v{c.derivation_version}
          </div>
        </div>
        <div className="summary">
          <Chip n={s.outstanding} label="Outstanding" tone="outstanding" />
          <Chip n={s.received} label="Received" tone="received" />
          <Chip n={s.needs_attention} label="Needs attention" tone="attention" />
          {s.waived > 0 && <Chip n={s.waived} label="Waived" tone="waived" />}
        </div>
      </header>

      {toast && <div className="toast">{toast}</div>}

      <div className="controls">
        <UploadBox clientId={clientId} onDone={(d) => withBusy(async () => {}, `Uploaded “${d.filename}” → ${d.status.replace("_", " ")}`)} />
        <FactsPanel
          people={people}
          facts={facts}
          runs={runs}
          disabled={busy}
          onDisclose={(personId, count, note) =>
            withBusy(async () => {
              await api.updateFact(clientId, { person_id: personId, tax_year: c.tax_year, employer_count: count, note });
              await api.rederive(clientId, note || "Re-derived after disclosure");
            }, "Re-derived — the expected list was updated without touching your edits")
          }
        />
      </div>

      <div className="board">
        <Column title="Outstanding" tone="outstanding" count={status.outstanding.length}>
          {status.outstanding.length === 0 && <Empty>Nothing outstanding.</Empty>}
          {status.outstanding.map((r) => (
            <OutstandingCard
              key={r.requirement_id}
              item={r}
              onWaive={(reason) => withBusy(() => api.waive(r.requirement_id, reason), "Marked not needed")}
              onRemove={() => withBusy(() => api.remove(r.requirement_id), "Removed the entry")}
            />
          ))}
        </Column>

        <Column title="Received" tone="received" count={status.received.length}>
          {status.received.length === 0 && <Empty>Nothing received yet.</Empty>}
          {status.received.map((r) => (
            <ReceivedCard
              key={r.requirement_id}
              item={r}
              onUnwaive={() => withBusy(() => api.unwaive(r.requirement_id), "Restored to outstanding")}
            />
          ))}
        </Column>

        <Column title="Needs attention" tone="attention" count={status.needs_attention.length}>
          {status.needs_attention.length === 0 && <Empty>Nothing to review.</Empty>}
          {status.needs_attention.map((d) => (
            <ReviewCard
              key={d.id}
              doc={d}
              people={people}
              onAccept={(body) => withBusy(() => api.accept(d.id, body), "Accepted")}
              onReject={(note) => withBusy(() => api.reject(d.id, note), "Rejected")}
            />
          ))}
        </Column>
      </div>
    </div>
  );
}

function Chip({ n, label, tone }) {
  return (
    <div className={`chip chip-${tone}`}>
      <span className="chip-n">{n}</span>
      <span className="chip-l">{label}</span>
    </div>
  );
}

function Column({ title, tone, count, children }) {
  return (
    <section className={`col col-${tone}`}>
      <h2>
        {title} <span className="col-count">{count}</span>
      </h2>
      <div className="col-body">{children}</div>
    </section>
  );
}

function Empty({ children }) {
  return <div className="empty">{children}</div>;
}

function UploadBox({ clientId, onDone }) {
  const [name, setName] = useState("");
  const onFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setName(file.name);
    const d = await api.upload(clientId, file);
    onDone(d);
    e.target.value = "";
    setName("");
  };
  return (
    <div className="panel">
      <h3>Add a document</h3>
      <p className="hint">Upload a file as it arrives. The tool reads it, guesses what it is, and either files it or sends it for review.</p>
      <label className="file-btn">
        {name || "Choose a file…"}
        <input type="file" onChange={onFile} hidden />
      </label>
    </div>
  );
}

function FactsPanel({ people, facts, runs, onDisclose, disabled }) {
  const byPerson = Object.fromEntries(facts.map((f) => [f.person_id, f]));
  const [personId, setPersonId] = useState("");
  const [count, setCount] = useState(2);
  const [note, setNote] = useState("Changed jobs in June 2025 (disclosed late)");

  return (
    <div className="panel">
      <h3>Disclose a change &amp; re-derive</h3>
      <p className="hint">
        Clients disclose things late. Change what we know about someone’s jobs and re-derive — new items appear, your edits stay put.
      </p>
      <div className="facts">
        {people.map((p) => (
          <div key={p.id} className="fact-row">
            <span>{p.name}</span>
            <span className="muted">
              {byPerson[p.id] ? `${byPerson[p.id].employer_count} employer(s)` : "no jobs on file"}
            </span>
          </div>
        ))}
      </div>
      <div className="disclose">
        <select value={personId} onChange={(e) => setPersonId(e.target.value)}>
          <option value="">Who changed?</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <input type="number" min="0" max="9" value={count} onChange={(e) => setCount(+e.target.value)} />
        <input className="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="note" />
        <button disabled={disabled || !personId} onClick={() => onDisclose(+personId, count, note)}>
          Re-derive
        </button>
      </div>
      {runs.length > 0 && (
        <div className="runs">
          <div className="runs-title">Derivation history</div>
          {runs.map((r) => (
            <div key={r.version} className="run">
              v{r.version} · {r.note} · +{r.added} new, {r.refreshed} refreshed
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function OutstandingCard({ item, onWaive, onRemove }) {
  return (
    <div className="card">
      <div className="card-title">
        {item.label}
        {item.source === "manual" && <span className="tag tag-manual">manual</span>}
        {item.no_longer_expected && <span className="tag tag-stale">no longer expected</span>}
      </div>
      <div className="card-actions">
        <button className="ghost" onClick={() => onWaive(prompt("Reason it's not needed?") || "Not needed")}>
          Mark not needed
        </button>
        <button className="ghost danger" onClick={() => window.confirm("Remove this entry?") && onRemove()}>
          Remove
        </button>
      </div>
    </div>
  );
}

function ReceivedCard({ item, onUnwaive }) {
  const waived = item.resolution === "waived";
  return (
    <div className={`card ${waived ? "card-waived" : "card-done"}`}>
      <div className="card-title">
        {item.label}
        {waived ? <span className="tag tag-waived">not needed</span> : <span className="tag tag-ok">received</span>}
      </div>
      {item.documents &&
        item.documents.map((d) => (
          <div key={d.id} className="doc-line">
            📄 {d.filename} <span className="muted">({Math.round(d.confidence * 100)}% sure)</span>
          </div>
        ))}
      {waived && (
        <div className="card-actions">
          {item.waived_reason && <div className="muted">{item.waived_reason}</div>}
          <button className="ghost" onClick={onUnwaive}>Restore</button>
        </div>
      )}
    </div>
  );
}

function ReviewCard({ doc, people, onAccept, onReject }) {
  const [kind, setKind] = useState(doc.guessed_kind || "");
  const [year, setYear] = useState(doc.guessed_tax_year || "");
  const [personId, setPersonId] = useState("");

  const conf = Math.round(doc.confidence * 100);
  return (
    <div className="card card-review">
      <div className="card-title">📄 {doc.filename}</div>
      <div className={`reason reason-${doc.review_reason}`}>{REASON_LABEL[doc.review_reason] || doc.review_reason}</div>

      <div className="guess">
        <div className="muted">The tool guessed:</div>
        <div>
          {doc.guessed_kind ? doc.guessed_kind.replace(/_/g, " ") : "unknown kind"}
          {doc.guessed_tax_year ? ` · ${doc.guessed_tax_year}` : ""}
          {doc.guessed_person_name ? ` · ${doc.guessed_person_name}` : ""}
        </div>
        <div className="confbar">
          <div className="confbar-fill" style={{ width: `${conf}%` }} />
        </div>
        <div className="muted">{conf}% confident{!doc.readable ? " · unreadable" : ""}</div>
      </div>

      <details className="correct">
        <summary>Correct &amp; accept</summary>
        <div className="correct-grid">
          <label>Kind
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="">—</option>
              {KIND_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <label>Year
            <input type="number" value={year} onChange={(e) => setYear(e.target.value)} />
          </label>
          <label>Person
            <select value={personId} onChange={(e) => setPersonId(e.target.value)}>
              <option value="">(auto)</option>
              {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
        </div>
        <button
          onClick={() =>
            onAccept({
              kind: kind || null,
              tax_year: year ? +year : null,
              person_id: personId ? +personId : null,
              note: "Corrected during review",
            })
          }
        >
          Save correction &amp; accept
        </button>
      </details>

      <div className="card-actions">
        <button onClick={() => onAccept({})}>Accept as-is</button>
        <button className="ghost danger" onClick={() => onReject(prompt("Reason for rejecting?") || "Rejected")}>
          Reject
        </button>
      </div>
    </div>
  );
}
