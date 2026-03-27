const el = (id) => document.getElementById(id);

const state = {
  collection: "",
};

// Modal Management
function openModal(modalId) {
  const modal = el(modalId);
  if (modal) {
    modal.style.display = "flex";
  }
}

function closeModal(modalId) {
  const modal = el(modalId);
  if (modal) {
    modal.style.display = "none";
  }
}

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
}

function clearWelcome() {
  const welcome = document.querySelector(".welcome");
  if (welcome) {
    welcome.remove();
  }
}

function addMessage(role, text, meta) {
  clearWelcome();
  
  const wrap = document.createElement("div");
  wrap.className = `msg msg--${role}`;
  
  const content = document.createElement("div");
  content.className = "msg__content";
  content.textContent = text;
  wrap.appendChild(content);

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
    cols = [];
  }

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = cols.length ? "Select collection" : "No collections";
  select.appendChild(placeholder);

  for (const c of cols) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    select.appendChild(opt);
  }

  if (state.collection && cols.includes(state.collection)) {
    select.value = state.collection;
  }
  
  return cols;
}

async function loadCollectionsList() {
  const container = el("collectionsList");
  if (!container) return;
  
  container.innerHTML = "";
  
  try {
    const cols = await fetchCollections();
    
    if (!cols.length) {
      container.innerHTML = '<p class="status">No collections found</p>';
      return;
    }
    
    for (const c of cols) {
      const card = document.createElement("div");
      card.className = "collection-card";
      if (c === state.collection) {
        card.classList.add("active");
      }
      
      const name = document.createElement("div");
      name.className = "collection-card__name";
      name.textContent = c;
      card.appendChild(name);
      
      card.addEventListener("click", () => {
        state.collection = c;
        el("collectionSelect").value = c;
        document.querySelectorAll(".collection-card").forEach(el => el.classList.remove("active"));
        card.classList.add("active");
      });
      
      container.appendChild(card);
    }
  } catch (e) {
    container.innerHTML = `<p class="status">Error loading collections: ${e.message}</p>`;
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
    del.className = "btn btn-secondary";
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
  // New chat button
  el("newChatBtn").addEventListener("click", () => {
    el("messages").innerHTML = '<div class="welcome"><h1>What can I help with?</h1></div>';
  });

  // Collection select
  el("collectionSelect").addEventListener("change", () => {
    const v = el("collectionSelect").value;
    setActiveCollection(v);
  });

  // Open file manager modal
  el("openFileManagerBtn").addEventListener("click", () => {
    openModal("fileManagerModal");
  });

  // Close file manager modal
  el("closeFileManagerBtn").addEventListener("click", () => {
    closeModal("fileManagerModal");
  });

  // Attach button (opens file manager)
  el("attachBtn").addEventListener("click", () => {
    openModal("fileManagerModal");
  });

  // Open collections modal
  el("manageCollectionsBtn").addEventListener("click", async () => {
    openModal("collectionsModal");
    await loadCollectionsList();
  });

  // Close collections modal
  el("closeCollectionsBtn").addEventListener("click", () => {
    closeModal("collectionsModal");
  });

  // Close modals when clicking overlay
  document.querySelectorAll(".modal__overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      const modal = e.target.closest(".modal");
      if (modal) {
        modal.style.display = "none";
      }
    });
  });

  // Create collection
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
      await loadCollectionsList();
      setActiveCollection(v);
      el("collectionSelect").value = v;
      el("newCollection").value = "";
    } catch (err) {
      alert(`Error creating collection: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  });

  // Upload form
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
    }
  });

  // Load documents
  el("loadDocs").addEventListener("click", async () => {
    try {
      const docs = await loadDocuments();
      renderDocs(docs);
    } catch (e) {
      alert(e.message);
    }
  });

  // Chat form
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

      const content = thinking.querySelector(".msg__content");
      if (content) {
        content.textContent = answer;
      }
      
      let metaDiv = thinking.querySelector(".msg__meta");
      if (!metaDiv) {
        metaDiv = document.createElement("div");
        metaDiv.className = "msg__meta";
        thinking.appendChild(metaDiv);
      }
      metaDiv.textContent = sourceMeta;
    } catch (err) {
      addMessage("assistant", `Error: ${err.message}`);
    }
  });

  // Auto-resize textarea
  const textarea = el("chatInput");
  textarea.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + "px";
  });
}

(async function init() {
  setActiveCollection("");
  wireEvents();
  await loadCollections();
})();
