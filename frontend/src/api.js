// Thin wrapper over fetch. Every call hits the FastAPI backend under /api.

async function j(res) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  clients: () => fetch("/api/clients").then(j),
  status: (id) => fetch(`/api/clients/${id}/status`).then(j),
  people: (id) => fetch(`/api/clients/${id}/people`).then(j),
  facts: (id) => fetch(`/api/clients/${id}/facts`).then(j),
  runs: (id) => fetch(`/api/clients/${id}/runs`).then(j),

  updateFact: (id, body) =>
    fetch(`/api/clients/${id}/facts`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(j),

  rederive: (id, note) =>
    fetch(`/api/clients/${id}/rederive`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    }).then(j),

  upload: (id, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`/api/clients/${id}/documents`, { method: "POST", body: fd }).then(j);
  },

  waive: (reqId, reason) =>
    fetch(`/api/requirements/${reqId}/waive`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }).then(j),

  unwaive: (reqId) => fetch(`/api/requirements/${reqId}/unwaive`, { method: "POST" }).then(j),
  remove: (reqId) => fetch(`/api/requirements/${reqId}/remove`, { method: "POST" }).then(j),

  addRequirement: (id, body) =>
    fetch(`/api/clients/${id}/requirements`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(j),

  accept: (docId, body) =>
    fetch(`/api/documents/${docId}/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(j),

  reject: (docId, note) =>
    fetch(`/api/documents/${docId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    }).then(j),
};
