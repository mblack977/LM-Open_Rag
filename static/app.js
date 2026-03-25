const el = (id) => document.getElementById(id);

const state = {
  collection: "",
};

function setStatus(text) {
  el("uploadStatus").textContent = text || "";
}

function showProgress(show) {
  el("uploadProgressWrap").style.display = show ? "block" : "none";
}

function setProgress(stage, current, total, message, logs) {
  const safeTotal = typeof total === "number" && total > 0 ? total : 0;
  const safeCurrent = typeof current === "number" && current >= 0 ? current : 0;
  const pct = safeTotal ? Math.min(100, Math.round((safeCurrent / safeTotal) * 100)) : 0;

  const stageLabel = (stage || "").toString();
  const msg = (message || "").toString();
  const left = msg ? `${stageLabel}: ${msg}` : stageLabel;

  el("uploadProgressText").textContent = left;
  el("uploadProgressPct").textContent = safeTotal ? `${pct}%` : "";
  el("uploadProgressBar").style.width = `${pct}%`;

  if (Array.isArray(logs)) {
    el("uploadLogs").textContent = logs.join("\n");
    el("uploadLogs").scrollTop = el("uploadLogs").scrollHeight;
  }
}

function setActiveCollection(name) {
  state.collection = name;
  el("activeCollection").textContent = name ? `Active collection: ${name}` : "No collection selected";
}

function addMessage(role, text, meta) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role === "user" ? "msg--user" : "msg--assistant"}`;
  wrap.textContent = text;

  if (meta) {
    const m = document.createElement("div");
    m.className = "msg__meta";
    m.textContent = meta;
    wrap.appendChild(m);
  }

  el("messages").appendChild(wrap);
  el("messages").scrollTop = el("messages").scrollHeight;
}

async function fetchCollections() {
  const resp = await fetch("/collections");
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Failed to load collections");
  return data.collections || [];
}

async function loadCollections() {
  const select = el("collectionSelect");
  select.innerHTML = "";

  let cols = [];
  try {
    cols = await fetchCollections();
  } catch (e) {
    // If Qdrant isn't reachable, show empty.
    cols = [];
  }

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = cols.length ? "Select collection" : "No collections (create/use one below)";
  select.appendChild(placeholder);

  for (const c of cols) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    select.appendChild(opt);
  }

  // Keep current selection if possible
  if (state.collection && cols.includes(state.collection)) {
    select.value = state.collection;
  } else if (!state.collection && cols.includes("MTSS_articles")) {
    select.value = "MTSS_articles";
    setActiveCollection("MTSS_articles");
  } else if (!state.collection && cols.includes("MTSS")) {
    select.value = "MTSS";
    setActiveCollection("MTSS");
  }
}

function currentCollection() {
  const fromSelect = el("collectionSelect").value;
  return (fromSelect || state.collection || "").trim();
}

async function uploadFile(file) {
  const collection = currentCollection();
  if (!collection) throw new Error("Pick a collection first");

  const fd = new FormData();
  fd.append("collection", collection);
  fd.append("file", file);

  const resp = await fetch("/upload_async", { method: "POST", body: fd });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Upload failed");
  return data;
}

async function fetchJob(jobId) {
  const resp = await fetch(`/jobs/${encodeURIComponent(jobId)}`);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Failed to get job");
  return data;
}

async function waitForJob(jobId) {
  const start = Date.now();
  const maxMs = 60 * 60 * 1000;

  while (true) {
    const job = await fetchJob(jobId);
    setProgress(job.stage, job.current, job.total, job.message, job.logs);

    if (job.status === "completed") return job;
    if (job.status === "failed") {
      throw new Error(job.error || job.message || "Job failed");
    }

    if (Date.now() - start > maxMs) throw new Error("Timed out waiting for job");
    await new Promise((r) => setTimeout(r, 800));
  }
}

async function queryRag(question) {
  const collection = currentCollection();
  if (!collection) throw new Error("Pick a collection first");

  const fd = new FormData();
  fd.append("collection", collection);
  fd.append("query", question);

  const resp = await fetch("/query", { method: "POST", body: fd });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Query failed");
  return data.response;
}

async function loadDocuments() {
  const collection = currentCollection();
  if (!collection) throw new Error("Pick a collection first");

  const resp = await fetch(`/documents?collection=${encodeURIComponent(collection)}`);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Failed to load documents");
  return data.documents || [];
}

async function deleteDocument(docId) {
  const collection = currentCollection();
  if (!collection) throw new Error("Pick a collection first");

  const resp = await fetch(`/documents/${encodeURIComponent(docId)}?collection=${encodeURIComponent(collection)}`, { method: "DELETE" });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Delete failed");
  return data;
}

function renderDocs(docs) {
  const container = el("docs");
  container.innerHTML = "";

  if (!docs.length) {
    const empty = document.createElement("div");
    empty.className = "status";
    empty.textContent = "No documents indexed in this collection.";
    container.appendChild(empty);
    return;
  }

  for (const d of docs) {
    const card = document.createElement("div");
    card.className = "doc";

    const title = document.createElement("div");
    title.className = "doc__title";
    title.textContent = d.filename || d.doc_id;

    const meta = document.createElement("div");
    meta.className = "doc__meta";
    meta.textContent = `doc_id: ${d.doc_id}`;

    const actions = document.createElement("div");
    actions.className = "doc__actions";

    const del = document.createElement("button");
    del.className = "btn btn--ghost";
    del.textContent = "Delete";
    del.onclick = async () => {
      del.disabled = true;
      try {
        await deleteDocument(d.doc_id);
        const updated = await loadDocuments();
        renderDocs(updated);
      } catch (e) {
        alert(e.message);
      } finally {
        del.disabled = false;
      }
    };

    actions.appendChild(del);
    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(actions);
    container.appendChild(card);
  }
}

function wireEvents() {
  el("refreshCollections").addEventListener("click", async () => {
    await loadCollections();
  });

  el("collectionSelect").addEventListener("change", () => {
    const v = el("collectionSelect").value;
    setActiveCollection(v);
  });

  el("createCollection").addEventListener("click", async () => {
    const v = el("newCollection").value.trim();
    if (!v) return;
    
    const btn = el("createCollection");
    btn.disabled = true;
    try {
      const resp = await fetch("/create_collection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collection: v })
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Failed to create collection");
      
      await loadCollections();
      setActiveCollection(v);
      el("collectionSelect").value = v;
      el("newCollection").value = "";
    } catch (err) {
      alert(`Error creating collection: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  });

  el("uploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = el("fileInput").files[0];
    if (!f) return;

    setStatus("Starting upload...");
    showProgress(true);
    setProgress("queued", 0, 0, "Queued", []);
    try {
      const data = await uploadFile(f);
      const jobId = data.job_id;
      setStatus(`Indexing started (job: ${jobId})`);
      const job = await waitForJob(jobId);
      const result = job.result || {};
      setStatus(`Done. Indexed ${result.chunks || ""} chunks.`.trim());
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    } finally {
      // Keep progress visible so user can read logs
    }
  });

  el("loadDocs").addEventListener("click", async () => {
    try {
      const docs = await loadDocuments();
      renderDocs(docs);
    } catch (e) {
      alert(e.message);
    }
  });

  el("chatForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = el("chatInput").value.trim();
    if (!text) return;

    el("chatInput").value = "";
    addMessage("user", text);

    try {
      addMessage("assistant", "Thinking...");
      const messagesEl = el("messages");
      const thinking = messagesEl.lastChild;

      const res = await queryRag(text);
      const answer = res.answer || "";
      const sources = res.sources || [];
      const sourceMeta = sources.length
        ? `Sources: ${sources.slice(0, 3).map(s => `${s.filename || s.doc_id}#${s.chunk_index}`).join(", ")}`
        : "Sources: none";

      thinking.textContent = answer;
      const metaDiv = document.createElement("div");
      metaDiv.className = "msg__meta";
      metaDiv.textContent = sourceMeta;
      thinking.appendChild(metaDiv);
    } catch (err) {
      addMessage("assistant", `Error: ${err.message}`);
    }
  });
}

(async function init() {
  setActiveCollection("");
  wireEvents();
  await loadCollections();
})();
