const el = (id) => document.getElementById(id);

const state = {
  collection: "",
  chatHistory: [],
  currentSessionId: null,
  sessions: [],
  retrievalProfile: "balanced",
  customWeights: {
    bm25: 0.30,
    fts: 0.20,
    vec: 0.50,
  },
  useReranker: false,
  normalizeScores: true,
  boostMetadata: false,
  currentAbortController: null,
};

// View Management
function showView(viewId) {
  const views = ["collectionsListView", "createCollectionView", "editCollectionView"];
  views.forEach(v => {
    const view = el(v);
    if (view) view.style.display = v === viewId ? "block" : "none";
  });
}

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
  const statusEl = el("uploadStatus");
  if (statusEl) {
    statusEl.textContent = text || "";
    // Make status more visible with styling based on content
    if (text.includes("✅") || text.includes("Success")) {
      statusEl.style.color = "#27ae60";
      statusEl.style.fontWeight = "600";
    } else if (text.includes("❌") || text.includes("Error")) {
      statusEl.style.color = "#e74c3c";
      statusEl.style.fontWeight = "600";
    } else {
      statusEl.style.color = "";
      statusEl.style.fontWeight = "";
    }
  }
}

function showProgress(show) {
  const progressEl = el("uploadProgressWrap");
  if (progressEl) {
    progressEl.style.display = show ? "block" : "none";
  }
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
  
  // Add to chat history
  state.chatHistory.push({ role, text, meta, timestamp: new Date().toISOString() });
  saveChatHistory();
}

function saveChatHistory() {
  try {
    localStorage.setItem("herbgpt_chat_history", JSON.stringify(state.chatHistory));
  } catch (e) {
    console.error("Failed to save chat history:", e);
  }
}

function loadChatHistory() {
  try {
    const saved = localStorage.getItem("herbgpt_chat_history");
    if (saved) {
      state.chatHistory = JSON.parse(saved);
      // Restore messages to UI
      state.chatHistory.forEach(msg => {
        const wrap = document.createElement("div");
        wrap.className = `msg msg--${msg.role}`;
        
        const content = document.createElement("div");
        content.className = "msg__content";
        content.textContent = msg.text;
        wrap.appendChild(content);

        if (msg.meta) {
          const m = document.createElement("div");
          m.className = "msg__meta";
          m.textContent = msg.meta;
          wrap.appendChild(m);
        }

        el("messages").appendChild(wrap);
      });
      
      if (state.chatHistory.length > 0) {
        clearWelcome();
      }
    }
  } catch (e) {
    console.error("Failed to load chat history:", e);
  }
}

function clearChatHistory() {
  state.chatHistory = [];
  localStorage.removeItem("herbgpt_chat_history");
  el("messages").innerHTML = '<div class="welcome"><h1>What can I help with?</h1></div>';
}

// Chat Session Management
async function createNewSession(title = "New Chat") {
  try {
    const resp = await fetch("/chat/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title,
        collection: state.collection || null
      })
    });
    
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Failed to create session");
    
    state.currentSessionId = data.session.session_id;
    await loadChatSessions();
    return data.session;
  } catch (e) {
    console.error("Failed to create session:", e);
    return null;
  }
}

async function loadChatSessions() {
  try {
    const resp = await fetch("/chat/sessions?limit=50");
    
    if (!resp.ok) {
      const errorText = await resp.text();
      console.error("Failed to load sessions - HTTP", resp.status, errorText);
      state.sessions = [];
      renderChatSessions();
      return;
    }
    
    const data = await resp.json();
    state.sessions = data.sessions || [];
    renderChatSessions();
  } catch (e) {
    console.error("Failed to load sessions:", e);
    state.sessions = [];
    renderChatSessions();
  }
}

function filterChatSessions(query) {
  if (!query) {
    renderChatSessions();
    return;
  }
  
  const filtered = state.sessions.filter(session => {
    return session.title.toLowerCase().includes(query) ||
           (session.collection && session.collection.toLowerCase().includes(query));
  });
  
  renderChatSessions(filtered);
}

function renderChatSessions(sessionsToRender = null) {
  const list = el("chatHistoryList");
  if (!list) return;
  
  const sessions = sessionsToRender || state.sessions;
  
  if (sessions.length === 0) {
    list.innerHTML = '<div class="chat-history-empty">No chat history yet</div>';
    return;
  }
  
  list.innerHTML = sessions.map(session => {
    const isActive = session.session_id === state.currentSessionId;
    const timeAgo = formatTimeAgo(session.last_message_at || session.created_at);
    
    return `
      <div class="chat-session-item ${isActive ? 'active' : ''}" data-session-id="${session.session_id}">
        <div class="chat-session-title" data-editable="false">${escapeHtml(session.title)}</div>
        <div class="chat-session-meta">
          <span>${session.message_count || 0} messages</span>
          <span>•</span>
          <span>${timeAgo}</span>
          ${session.collection ? `<span class="chat-collection-badge">${escapeHtml(session.collection)}</span>` : ''}
        </div>
        <div class="chat-session-actions">
          <button class="chat-action-btn" data-action="rename" title="Rename">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </button>
          <button class="chat-action-btn" data-action="delete" title="Delete">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      </div>
    `;
  }).join('');
  
  // Attach event listeners
  list.querySelectorAll('.chat-session-item').forEach(item => {
    const sessionId = item.dataset.sessionId;
    
    item.addEventListener('click', (e) => {
      if (e.target.closest('.chat-action-btn')) return;
      switchToSession(sessionId);
    });
    
    item.querySelector('[data-action="rename"]')?.addEventListener('click', (e) => {
      e.stopPropagation();
      startRenameSession(sessionId, item);
    });
    
    item.querySelector('[data-action="delete"]')?.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteSession(sessionId);
    });
  });
}

async function switchToSession(sessionId) {
  if (sessionId === state.currentSessionId) return;
  
  try {
    const resp = await fetch(`/chat/sessions/${sessionId}/messages`);
    const data = await resp.json();
    
    if (!resp.ok) throw new Error(data.detail || "Failed to load messages");
    
    // Clear current chat
    el("messages").innerHTML = '';
    state.chatHistory = [];
    state.currentSessionId = sessionId;
    
    // Load messages
    const messages = data.messages || [];
    messages.forEach(msg => {
      addMessage(msg.role, msg.content, msg.sources ? formatSources(msg.sources) : null);
    });
    
    if (messages.length === 0) {
      el("messages").innerHTML = '<div class="welcome"><h1>What can I help with?</h1></div>';
    }
    
    renderChatSessions();
  } catch (e) {
    console.error("Failed to switch session:", e);
    alert(`Error loading chat: ${e.message}`);
  }
}

async function saveMessageToSession(role, content, sources = null) {
  if (!state.currentSessionId) {
    const title = role === 'user' ? generateTitleFromMessage(content) : 'New Chat';
    await createNewSession(title);
  }
  
  if (!state.currentSessionId) return;
  
  try {
    await fetch(`/chat/sessions/${state.currentSessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role,
        content,
        sources,
        retrieval_profile: state.retrievalProfile
      })
    });
    
    await loadChatSessions();
  } catch (e) {
    console.error("Failed to save message:", e);
  }
}

function generateTitleFromMessage(message) {
  const words = message.trim().split(/\s+/);
  if (words.length <= 6) return message;
  return words.slice(0, 6).join(' ') + '...';
}

function formatSources(sources) {
  if (!sources || !Array.isArray(sources)) return null;
  return sources.map(s => `${s.doc_name || 'Unknown'} (${s.score?.toFixed(2) || 'N/A'})`).join(', ');
}

function startRenameSession(sessionId, itemEl) {
  const titleEl = itemEl.querySelector('.chat-session-title');
  const currentTitle = titleEl.textContent;
  
  titleEl.innerHTML = `<input type="text" class="chat-session-title-input" value="${escapeHtml(currentTitle)}" />`;
  const input = titleEl.querySelector('input');
  input.focus();
  input.select();
  
  const finishRename = async () => {
    const newTitle = input.value.trim();
    if (newTitle && newTitle !== currentTitle) {
      await renameSession(sessionId, newTitle);
    }
    await loadChatSessions();
  };
  
  input.addEventListener('blur', finishRename);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      input.blur();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      loadChatSessions();
    }
  });
}

async function renameSession(sessionId, newTitle) {
  try {
    await fetch(`/chat/sessions/${sessionId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle })
    });
  } catch (e) {
    console.error("Failed to rename session:", e);
  }
}

async function deleteSession(sessionId) {
  if (!confirm('Delete this chat? This cannot be undone.')) return;
  
  try {
    await fetch(`/chat/sessions/${sessionId}`, { method: "DELETE" });
    
    if (sessionId === state.currentSessionId) {
      state.currentSessionId = null;
      clearChatHistory();
    }
    
    await loadChatSessions();
  } catch (e) {
    console.error("Failed to delete session:", e);
    alert(`Error deleting chat: ${e.message}`);
  }
}

function formatTimeAgo(timestamp) {
  if (!timestamp) return 'Just now';
  
  const now = new Date();
  const then = new Date(timestamp);
  const seconds = Math.floor((now - then) / 1000);
  
  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return then.toLocaleDateString();
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function fetchCollections() {
  const resp = await fetch("/collections");
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Failed to load collections");
  return data.collections || [];
}

async function loadCustomProfiles() {
  try {
    const resp = await fetch("/retrieval/profiles");
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Failed to load profiles");
    
    const profiles = data.profiles || [];
    const customProfiles = profiles.filter(p => !p.is_system);
    
    // Update profile selector with custom profiles
    const select = el("retrievalProfileSelect");
    if (!select) return;
    
    // Remove old custom options
    const options = Array.from(select.options);
    options.forEach(opt => {
      if (opt.value !== "balanced" && opt.value !== "keyword_heavy" && 
          opt.value !== "conceptual" && opt.value !== "academic_evidence" && 
          opt.value !== "custom") {
        opt.remove();
      }
    });
    
    // Add custom profiles before "Custom" option
    const customOption = select.querySelector('option[value="custom"]');
    customProfiles.forEach(profile => {
      const opt = document.createElement("option");
      opt.value = profile.profile_name;
      opt.textContent = profile.display_name;
      if (customOption) {
        select.insertBefore(opt, customOption);
      } else {
        select.appendChild(opt);
      }
      
      // Add to descriptions and weights
      PROFILE_DESCRIPTIONS[profile.profile_name] = profile.description || "Custom saved profile";
      PROFILE_WEIGHTS[profile.profile_name] = {
        bm25: profile.bm25_weight,
        fts: profile.pg_fts_weight,
        vec: profile.pg_vec_weight,
      };
    });
  } catch (e) {
    console.error("Failed to load custom profiles:", e);
  }
}

async function loadCollections() {
  const select = el("collectionSelect");
  select.innerHTML = "";

  let cols = [];
  try {
    const resp = await fetch("/collections");
    const data = await resp.json();
    cols = data.collections || [];
  } catch (e) {
    cols = [];
  }

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = cols.length ? "Select collection" : "No collections";
  select.appendChild(placeholder);

  for (const c of cols) {
    const opt = document.createElement("option");
    opt.value = c.name;
    opt.textContent = c.display_name || c.name;
    select.appendChild(opt);
  }

  if (state.collection) {
    const found = cols.find(c => c.name === state.collection);
    if (found) {
      select.value = state.collection;
    }
  }
  
  return cols;
}

async function loadCollectionsList() {
  const container = el("collectionsList");
  if (!container) return;
  
  container.innerHTML = "";
  
  try {
    const resp = await fetch("/collections");
    const data = await resp.json();
    const cols = data.collections || [];
    
    if (!cols.length) {
      container.innerHTML = '<p class="status">No collections found</p>';
      return;
    }
    
    for (const c of cols) {
      const card = document.createElement("div");
      card.className = "collection-card";
      if (c.name === state.collection) {
        card.classList.add("active");
      }
      
      // Image section
      const imageDiv = document.createElement("div");
      imageDiv.className = "collection-card__image";
      
      if (c.image) {
        const img = document.createElement("img");
        img.src = `/collections/${c.name}/image`;
        img.alt = c.display_name || c.name;
        imageDiv.appendChild(img);
      } else {
        const placeholder = document.createElement("div");
        placeholder.className = "collection-card__image-placeholder";
        placeholder.textContent = (c.display_name || c.name).charAt(0).toUpperCase();
        imageDiv.appendChild(placeholder);
      }
      card.appendChild(imageDiv);
      
      // Edit button
      const editBtn = document.createElement("button");
      editBtn.className = "collection-card__edit-btn";
      editBtn.textContent = "Edit";
      editBtn.onclick = (e) => {
        e.stopPropagation();
        openEditView(c);
      };
      card.appendChild(editBtn);
      
      // Content section
      const content = document.createElement("div");
      content.className = "collection-card__content";
      
      const name = document.createElement("div");
      name.className = "collection-card__name";
      name.textContent = c.display_name || c.name;
      content.appendChild(name);
      
      if (c.description) {
        const desc = document.createElement("div");
        desc.className = "collection-card__description";
        desc.textContent = c.description;
        content.appendChild(desc);
      }
      
      const meta = document.createElement("div");
      meta.className = "collection-card__meta";
      meta.textContent = `${c.file_count || 0} files`;
      content.appendChild(meta);
      
      card.appendChild(content);
      
      card.addEventListener("click", () => {
        state.collection = c.name;
        el("collectionSelect").value = c.name;
        document.querySelectorAll(".collection-card").forEach(el => el.classList.remove("active"));
        card.classList.add("active");
      });
      
      container.appendChild(card);
    }
  } catch (e) {
    container.innerHTML = `<p class="status">Error loading collections: ${e.message}</p>`;
  }
}

async function openEditView(collection) {
  showView("editCollectionView");
  
  // Populate form
  el("editCollectionId").value = collection.name;
  el("editCollectionName").value = collection.display_name || collection.name;
  el("editCollectionDescription").value = collection.description || "";
  
  // Show current image if exists
  const preview = el("editImagePreview");
  const previewImg = el("editPreviewImg");
  if (collection.image) {
    previewImg.src = `/collections/${collection.name}/image`;
    preview.style.display = "block";
  } else {
    preview.style.display = "none";
  }
  
  // Set active collection for file uploads
  state.collection = collection.name;
  
  // Clear any previous file selection
  const fileInput = el("fileInput");
  if (fileInput) fileInput.value = "";
  
  // Auto-load documents for this collection
  try {
    const docs = await loadDocuments();
    renderDocs(docs);
  } catch (e) {
    console.error("Failed to load documents:", e);
    const docsContainer = el("docs");
    if (docsContainer) {
      docsContainer.innerHTML = `<div class="status" style="color: #e74c3c;">Error loading documents: ${e.message}</div>`;
    }
  }
  
  console.log("Edit view opened for collection:", collection.name);
}

function currentCollection() {
  const fromSelect = el("collectionSelect").value;
  return (fromSelect || state.collection || "").trim();
}

async function uploadFile(file) {
  const collection = currentCollection();
  console.log("uploadFile called:", { filename: file.name, collection });
  
  if (!collection) {
    const error = "Pick a collection first";
    console.error(error);
    throw new Error(error);
  }

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

async function waitForJobWithProgress(jobId, progressCallback) {
  const start = Date.now();
  const maxMs = 60 * 60 * 1000;
  let lastStage = "";

  while (true) {
    const job = await fetchJob(jobId);
    
    // Update progress with detailed stage information
    const stageEmoji = {
      "queued": "⏳",
      "processing": "📄",
      "embedding": "🧠",
      "upserting": "💾",
      "completed": "✅",
      "failed": "❌"
    };
    
    const emoji = stageEmoji[job.stage] || "⚙️";
    const displayStage = `${emoji} ${job.stage.charAt(0).toUpperCase() + job.stage.slice(1)}`;
    
    if (progressCallback) {
      progressCallback(displayStage, job.current, job.total, job.message, job.logs);
    }
    
    // Log stage transitions
    if (job.stage !== lastStage) {
      console.log(`Job ${jobId}: ${job.stage} (${job.current}/${job.total})`);
      lastStage = job.stage;
    }

    if (job.status === "completed") return job;
    if (job.status === "failed") {
      throw new Error(job.error || job.message || "Job failed");
    }

    if (Date.now() - start > maxMs) throw new Error("Timed out waiting for job");
    await new Promise((r) => setTimeout(r, 800));
  }
}

async function waitForJob(jobId) {
  return waitForJobWithProgress(jobId, (stage, current, total, message, logs) => {
    setProgress(stage, current, total, message, logs);
  });
}

async function queryRag(question) {
  const collection = currentCollection();
  if (!collection) throw new Error("Pick a collection first");

  // Save user message to session
  await saveMessageToSession('user', question);

  const fd = new FormData();
  fd.append("collection", collection);
  fd.append("query", question);
  
  // Add retrieval profile or custom weights
  if (state.retrievalProfile !== "custom") {
    fd.append("profile_name", state.retrievalProfile);
  } else {
    // Use custom weights
    fd.append("bm25_weight", state.customWeights.bm25);
    fd.append("pg_fts_weight", state.customWeights.fts);
    fd.append("pg_vec_weight", state.customWeights.vec);
    fd.append("use_reranker", state.useReranker);
    fd.append("normalize_scores", state.normalizeScores);
  }

  // Create abort controller for this request
  state.currentAbortController = new AbortController();
  
  const resp = await fetch("/query", { 
    method: "POST", 
    body: fd,
    signal: state.currentAbortController.signal
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Query failed");
  
  // Save assistant response to session
  const sources = data.sources || [];
  await saveMessageToSession('assistant', data.response, sources);
  
  state.currentAbortController = null;
  return data;
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

function renderDocsToContainer(docs, container) {
  if (!container) return;
  
  container.innerHTML = "";

  if (!docs || !docs.length) {
    const empty = document.createElement("div");
    empty.className = "status";
    empty.innerHTML = `
      <div style="text-align: center; padding: 20px;">
        <p style="margin-bottom: 12px;">No documents indexed in this collection.</p>
        <p style="font-size: 12px; color: var(--text-light);">Upload a file above to get started.</p>
      </div>
    `;
    container.appendChild(empty);
    return;
  }

  for (const d of docs) {
    const card = document.createElement("div");
    card.className = "doc";

    const title = document.createElement("div");
    title.className = "doc__title";
    title.textContent = d.filename || d.title || d.doc_id;

    const meta = document.createElement("div");
    meta.className = "doc__meta";
    const fileSize = d.file_size ? ` • ${(d.file_size / 1024).toFixed(1)} KB` : '';
    const createdAt = d.created_at ? ` • ${new Date(d.created_at).toLocaleDateString()}` : '';
    meta.textContent = `${d.doc_id.substring(0, 8)}...${fileSize}${createdAt}`;

    const actions = document.createElement("div");
    actions.className = "doc__actions";

    const del = document.createElement("button");
    del.className = "btn btn-secondary";
    del.textContent = "Delete";
    del.onclick = async () => {
      if (!confirm(`Delete "${d.filename || d.title}"?`)) return;
      del.disabled = true;
      del.textContent = "Deleting...";
      try {
        await deleteDocument(d.doc_id);
        const updated = await loadDocuments();
        renderDocsToContainer(updated, container);
      } catch (e) {
        alert(`Error deleting document: ${e.message}`);
        del.disabled = false;
        del.textContent = "Delete";
      }
    };

    actions.appendChild(del);
    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(actions);
    container.appendChild(card);
  }
  
  // Add count header
  const countHeader = document.createElement("div");
  countHeader.style.cssText = "margin-bottom: 12px; font-size: 14px; color: var(--text-light); font-weight: 500;";
  countHeader.textContent = `${docs.length} document${docs.length !== 1 ? 's' : ''} indexed`;
  container.insertBefore(countHeader, container.firstChild);
}

function renderDocs(docs) {
  const container = el("docs");
  renderDocsToContainer(docs, container);
}

// Retrieval Profile Management
const PROFILE_DESCRIPTIONS = {
  balanced: "Balanced approach combining keyword matching and semantic understanding. Good general-purpose profile.",
  keyword_heavy: "Prioritizes exact keyword matching. Best for queries with specific terminology or technical terms.",
  conceptual: "Emphasizes semantic similarity. Best for conceptual queries and finding related ideas.",
  academic_evidence: "Optimized for finding empirical evidence and research findings. Balanced with slight semantic preference.",
  custom: "Uses your saved manual configuration."
};

const PROFILE_WEIGHTS = {
  balanced: { bm25: 0.30, fts: 0.20, vec: 0.50 },
  keyword_heavy: { bm25: 0.60, fts: 0.25, vec: 0.15 },
  conceptual: { bm25: 0.15, fts: 0.15, vec: 0.70 },
  academic_evidence: { bm25: 0.25, fts: 0.15, vec: 0.60 },
};

function normalizeWeights() {
  const bm25 = parseFloat(el("bm25Weight").value) / 100;
  const fts = parseFloat(el("ftsWeight").value) / 100;
  const vec = parseFloat(el("vecWeight").value) / 100;
  
  const total = bm25 + fts + vec;
  if (total === 0) return { bm25: 0.33, fts: 0.33, vec: 0.34 };
  
  return {
    bm25: bm25 / total,
    fts: fts / total,
    vec: vec / total,
  };
}

function updateWeightDisplays() {
  const normalized = normalizeWeights();
  const bm25El = el("bm25WeightValue");
  const ftsEl = el("ftsWeightValue");
  const vecEl = el("vecWeightValue");
  
  if (bm25El) bm25El.textContent = normalized.bm25.toFixed(2);
  if (ftsEl) ftsEl.textContent = normalized.fts.toFixed(2);
  if (vecEl) vecEl.textContent = normalized.vec.toFixed(2);
  
  state.customWeights = normalized;
}

function loadProfileWeights(profileName) {
  if (profileName === "custom") return;
  
  const weights = PROFILE_WEIGHTS[profileName];
  if (!weights) return;
  
  const bm25Slider = el("bm25Weight");
  const ftsSlider = el("ftsWeight");
  const vecSlider = el("vecWeight");
  
  if (bm25Slider) bm25Slider.value = Math.round(weights.bm25 * 100);
  if (ftsSlider) ftsSlider.value = Math.round(weights.fts * 100);
  if (vecSlider) vecSlider.value = Math.round(weights.vec * 100);
  
  updateWeightDisplays();
}

function updateProfileDescription(profileName) {
  const desc = PROFILE_DESCRIPTIONS[profileName] || "";
  const descEl = el("profileDescription");
  if (descEl) {
    descEl.textContent = desc;
  }
}

function wireEvents() {
  // New chat button
  const newChatBtn = el("newChatBtn");
  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
      state.currentSessionId = null;
      clearChatHistory();
    });
  }
  
  // Search chats button
  const searchChatsBtn = el("searchChatsBtn");
  if (searchChatsBtn) {
    searchChatsBtn.addEventListener("click", () => {
      const searchBox = el("chatSearchBox");
      if (searchBox) {
        const isVisible = searchBox.style.display !== "none";
        searchBox.style.display = isVisible ? "none" : "block";
        if (!isVisible) {
          el("chatSearchInput")?.focus();
        }
      }
    });
  }
  
  // Search chats input
  const searchInput = el("chatSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase().trim();
      filterChatSessions(query);
    });
  }
  
  // Retrieval profile selector
  const profileSelect = el("retrievalProfileSelect");
  if (profileSelect) {
    profileSelect.addEventListener("change", (e) => {
      const profileName = e.target.value;
      state.retrievalProfile = profileName;
      updateProfileDescription(profileName);
      loadProfileWeights(profileName);
    });
  }
  
  // Advanced tuning toggle
  const advancedBtn = el("advancedTuningBtn");
  if (advancedBtn) {
    advancedBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const panel = el("advancedTuningPanel");
      if (panel) {
        const isVisible = panel.style.display !== "none";
        panel.style.display = isVisible ? "none" : "block";
      }
    });
  }
  
  // Weight sliders
  ["bm25Weight", "ftsWeight", "vecWeight"].forEach(id => {
    el(id).addEventListener("input", updateWeightDisplays);
  });
  
  // Method toggles
  el("methodBM25").addEventListener("change", (e) => {
    if (!e.target.checked) {
      el("bm25Weight").value = 0;
      updateWeightDisplays();
    }
  });
  
  el("methodFTS").addEventListener("change", (e) => {
    if (!e.target.checked) {
      el("ftsWeight").value = 0;
      updateWeightDisplays();
    }
  });
  
  el("methodVec").addEventListener("change", (e) => {
    if (!e.target.checked) {
      el("vecWeight").value = 0;
      updateWeightDisplays();
    }
  });
  
  // Options checkboxes
  el("normalizeScores").addEventListener("change", (e) => {
    state.normalizeScores = e.target.checked;
  });
  
  el("useReranker").addEventListener("change", (e) => {
    state.useReranker = e.target.checked;
  });
  
  el("boostMetadata").addEventListener("change", (e) => {
    state.boostMetadata = e.target.checked;
  });
  
  // Apply profile button
  el("applyProfileBtn").addEventListener("click", () => {
    state.retrievalProfile = "custom";
    el("retrievalProfileSelect").value = "custom";
    updateProfileDescription("custom");
    alert("Custom retrieval settings applied. Your next query will use these settings.");
  });
  
  // Save profile button - open modal
  const saveProfileBtn = el("saveProfileBtn");
  if (saveProfileBtn) {
    saveProfileBtn.addEventListener("click", () => {
      const normalized = normalizeWeights();
      
      // Update modal with current settings
      const saveBM25 = el("saveBM25Value");
      const saveFTS = el("saveFTSValue");
      const saveVec = el("saveVecValue");
      const saveReranker = el("saveRerankerValue");
      const saveNormalize = el("saveNormalizeValue");
      
      if (saveBM25) saveBM25.textContent = normalized.bm25.toFixed(2);
      if (saveFTS) saveFTS.textContent = normalized.fts.toFixed(2);
      if (saveVec) saveVec.textContent = normalized.vec.toFixed(2);
      if (saveReranker) saveReranker.textContent = state.useReranker ? "On" : "Off";
      if (saveNormalize) saveNormalize.textContent = state.normalizeScores ? "On" : "Off";
      
      openModal("saveProfileModal");
    });
  }
  
  // Close save profile modal
  const closeSaveProfileBtn = el("closeSaveProfileBtn");
  if (closeSaveProfileBtn) {
    closeSaveProfileBtn.addEventListener("click", () => {
      closeModal("saveProfileModal");
    });
  }
  
  const cancelSaveProfileBtn = el("cancelSaveProfileBtn");
  if (cancelSaveProfileBtn) {
    cancelSaveProfileBtn.addEventListener("click", () => {
      closeModal("saveProfileModal");
    });
  }
  
  // Save profile form submission
  const saveProfileForm = el("saveProfileForm");
  if (saveProfileForm) {
    saveProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      
      const profileName = el("profileName").value.trim();
      const displayName = el("profileDisplayName").value.trim();
      const description = el("profileDesc").value.trim();
      
      if (!profileName || !displayName) {
        alert("Profile name and display name are required");
        return;
      }
      
      const normalized = normalizeWeights();
      const profileData = {
        profile_name: profileName.toLowerCase().replace(/\s+/g, "_"),
        display_name: displayName,
        description: description,
        is_system: false,
        is_active: true,
        bm25_weight: normalized.bm25,
        pg_fts_weight: normalized.fts,
        pg_vec_weight: normalized.vec,
        use_reranker: state.useReranker,
        reranker_model: null,
        normalize_scores: state.normalizeScores,
        metadata_boost: state.boostMetadata ? 0.1 : 0.0,
        citation_graph_boost: 0.0,
        top_k: 10,
        bm25_limit: 30,
        fts_limit: 30,
        vec_limit: 30,
      };
      
      try {
        const resp = await fetch("/retrieval/profiles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(profileData),
        });
        
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || data.message || "Failed to save profile");
        
        closeModal("saveProfileModal");
        saveProfileForm.reset();
        
        // Reload profiles
        await loadCustomProfiles();
        
        alert(`Profile "${displayName}" saved successfully!`);
      } catch (err) {
        alert(`Error saving profile: ${err.message}`);
      }
    });
  }

  // Collection select
  el("collectionSelect").addEventListener("change", () => {
    const v = el("collectionSelect").value;
    setActiveCollection(v);
  });

  // Open collections modal
  el("manageCollectionsBtn").addEventListener("click", async () => {
    openModal("collectionsModal");
    showView("collectionsListView");
    await loadCollectionsList();
  });

  // Close collections modal
  el("closeCollectionsBtn").addEventListener("click", () => {
    closeModal("collectionsModal");
  });

  // Show create collection view
  el("showCreateCollectionBtn").addEventListener("click", () => {
    showView("createCollectionView");
  });

  // Back to list buttons
  el("backToListBtn").addEventListener("click", () => {
    showView("collectionsListView");
  });

  el("backToListFromEditBtn").addEventListener("click", () => {
    showView("collectionsListView");
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

  // Image preview for collection creation
  const imageInput = el("collectionImage");
  if (imageInput) {
    imageInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      const preview = el("imagePreview");
      const previewImg = el("previewImg");
      
      if (file && file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => {
          previewImg.src = e.target.result;
          preview.style.display = "block";
        };
        reader.readAsDataURL(file);
      } else {
        preview.style.display = "none";
      }
    });
  }

  // Image preview for collection editing
  const editImageInput = el("editCollectionImage");
  if (editImageInput) {
    editImageInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      const preview = el("editImagePreview");
      const previewImg = el("editPreviewImg");
      
      if (file && file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => {
          previewImg.src = e.target.result;
          preview.style.display = "block";
        };
        reader.readAsDataURL(file);
      } else {
        preview.style.display = "none";
      }
    });
  }

  // Create collection form
  const createForm = el("createCollectionForm");
  if (createForm) {
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      
      const formData = new FormData(createForm);
      const submitBtn = createForm.querySelector('button[type="submit"]');
      
      submitBtn.disabled = true;
      submitBtn.textContent = "Creating...";
      
      try {
        const resp = await fetch("/collections", {
          method: "POST",
          body: formData
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Failed to create collection");
        
        await loadCollections();
        await loadCollectionsList();
        
        setActiveCollection(data.collection);
        el("collectionSelect").value = data.collection;
        
        createForm.reset();
        el("imagePreview").style.display = "none";
        
        showView("collectionsListView");
        alert(`Collection "${data.metadata.name}" created successfully!`);
      } catch (err) {
        alert(`Error creating collection: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Create Collection";
      }
    });
  }

  // Edit collection form
  const editForm = el("editCollectionForm");
  if (editForm) {
    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      
      const collectionId = el("editCollectionId").value;
      const formData = new FormData(editForm);
      const submitBtn = editForm.querySelector('button[type="submit"]');
      
      submitBtn.disabled = true;
      submitBtn.textContent = "Saving...";
      
      try {
        const resp = await fetch(`/collections/${collectionId}`, {
          method: "PUT",
          body: formData
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Failed to update collection");
        
        await loadCollections();
        await loadCollectionsList();
        
        if (data.new_name !== data.old_name) {
          setActiveCollection(data.new_name);
          el("collectionSelect").value = data.new_name;
        }
        
        showView("collectionsListView");
        alert("Collection updated successfully!");
      } catch (err) {
        alert(`Error updating collection: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Save Changes";
      }
    });
  }

  // Helper function to handle upload form submission
  async function handleUploadSubmit(e, fileInputId, statusId, progressWrapId, progressTextId, progressPctId, progressBarId, logsId, docsId) {
    e.preventDefault();
    e.stopPropagation();
    
    console.log("Upload form submitted:", {
      formId: e.target.id,
      fileInputId,
      collection: currentCollection()
    });
    
    const f = el(fileInputId).files[0];
    if (!f) {
      console.warn("No file selected");
      alert("Please select a file to upload");
      return;
    }
    
    console.log("File selected:", f.name, f.size, "bytes");

    const submitBtn = e.target.querySelector('button[type="submit"]');
    const fileInput = el(fileInputId);
    
    submitBtn.disabled = true;
    submitBtn.textContent = "Uploading...";
    fileInput.disabled = true;

    // Helper functions for this specific form
    const setFormStatus = (text) => {
      const statusEl = el(statusId);
      if (statusEl) {
        statusEl.textContent = text || "";
        if (text.includes("✅") || text.includes("Success")) {
          statusEl.style.color = "#27ae60";
          statusEl.style.fontWeight = "600";
        } else if (text.includes("❌") || text.includes("Error")) {
          statusEl.style.color = "#e74c3c";
          statusEl.style.fontWeight = "600";
        } else {
          statusEl.style.color = "";
          statusEl.style.fontWeight = "";
        }
      }
    };

    const showFormProgress = (show) => {
      const progressEl = el(progressWrapId);
      if (progressEl) {
        progressEl.style.display = show ? "block" : "none";
      }
    };

    const setFormProgress = (stage, current, total, message, logs) => {
      const safeTotal = typeof total === "number" && total > 0 ? total : 0;
      const safeCurrent = typeof current === "number" && current >= 0 ? current : 0;
      const pct = safeTotal ? Math.min(100, Math.round((safeCurrent / safeTotal) * 100)) : 0;

      const stageLabel = (stage || "").toString();
      const msg = (message || "").toString();
      const left = msg ? `${stageLabel}: ${msg}` : stageLabel;

      const textEl = el(progressTextId);
      const pctEl = el(progressPctId);
      const barEl = el(progressBarId);
      const logsEl = el(logsId);

      if (textEl) textEl.textContent = left;
      if (pctEl) pctEl.textContent = safeTotal ? `${pct}%` : "";
      if (barEl) barEl.style.width = `${pct}%`;

      if (Array.isArray(logs) && logsEl) {
        logsEl.textContent = logs.join("\n");
        logsEl.scrollTop = logsEl.scrollHeight;
      }
    };

    setFormStatus(`📤 Uploading "${f.name}"...`);
    showFormProgress(true);
    setFormProgress("uploading", 0, 1, "Uploading file to server", []);
    
    try {
      console.log("Starting upload for:", f.name);
      const data = await uploadFile(f);
      console.log("Upload response:", data);
      
      const jobId = data.job_id;
      if (!jobId) {
        throw new Error("No job ID returned from server");
      }
      
      setFormStatus(`⚙️ Processing "${f.name}" - Job ID: ${jobId}`);
      setFormProgress("processing", 0, 1, "Starting document processing", [`Job ${jobId} created`]);
      
      // Wait for job with custom progress updates
      const job = await waitForJobWithProgress(jobId, setFormProgress);
      const result = job.result || {};
      const chunks = result.chunks || 0;
      const filename = result.filename || f.name;
      
      setFormStatus(`✅ Success! "${filename}" indexed with ${chunks} chunk${chunks !== 1 ? 's' : ''}`);
      setFormProgress("completed", 1, 1, "Indexing complete", job.logs || []);
      
      // Clear file input
      fileInput.value = "";
      
      // Refresh document list
      try {
        const docs = await loadDocuments();
        if (docsId) {
          const docsContainer = el(docsId);
          if (docsContainer) {
            renderDocsToContainer(docs, docsContainer);
          }
        } else {
          renderDocs(docs);
        }
      } catch (e) {
        console.error("Failed to refresh documents:", e);
      }
      
      // Auto-hide progress after 3 seconds on success
      setTimeout(() => {
        showFormProgress(false);
      }, 3000);
      
    } catch (err) {
      setFormStatus(`❌ Error: ${err.message}`);
      setFormProgress("failed", 0, 1, `Failed: ${err.message}`, []);
      console.error("Upload error:", err);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Upload & Index";
      fileInput.disabled = false;
    }
  }

  // Use event delegation for upload forms to handle forms in modals
  document.addEventListener("submit", (e) => {
    console.log("Form submitted:", e.target.id, e.target.className);
    
    // Edit collection view upload form
    if (e.target.id === "uploadForm") {
      console.log("Handling uploadForm submission");
      handleUploadSubmit(
        e, "fileInput", "uploadStatus", "uploadProgressWrap",
        "uploadProgressText", "uploadProgressPct", "uploadProgressBar", "uploadLogs", "docs"
      );
      return;
    }
    // File manager modal upload form
    if (e.target.id === "fileManagerUploadForm") {
      console.log("Handling fileManagerUploadForm submission");
      handleUploadSubmit(
        e, "fileManagerFileInput", "fileManagerUploadStatus", "fileManagerUploadProgressWrap",
        "fileManagerUploadProgressText", "fileManagerUploadProgressPct", "fileManagerUploadProgressBar",
        "fileManagerUploadLogs", "fileManagerDocs"
      );
      return;
    }
  }, true); // Use capture phase to catch it early

  // Load documents button in edit collection view
  const loadDocsBtn = el("loadDocs");
  if (loadDocsBtn) {
    loadDocsBtn.addEventListener("click", async () => {
      try {
        const docs = await loadDocuments();
        renderDocs(docs);
      } catch (e) {
        alert(e.message);
      }
    });
  }

  // Load documents button in file manager modal
  const fileManagerLoadDocsBtn = el("fileManagerLoadDocs");
  if (fileManagerLoadDocsBtn) {
    fileManagerLoadDocsBtn.addEventListener("click", async () => {
      try {
        const docs = await loadDocuments();
        const docsContainer = el("fileManagerDocs");
        renderDocsToContainer(docs, docsContainer);
      } catch (e) {
        alert(e.message);
      }
    });
  }

  // Chat form with Enter/Shift+Enter support
  const chatInput = el("chatInput");
  const chatForm = el("chatForm");
  
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = "";
    chatInput.style.height = "auto";
    addMessage("user", text);

    const sendBtn = el("sendBtn");
    const stopBtn = el("stopBtn");
    
    // Show stop button, hide send button
    sendBtn.style.display = "none";
    stopBtn.style.display = "flex";

    try {
      addMessage("assistant", "Thinking...");
      const messagesEl = el("messages");
      const thinking = messagesEl.lastChild;

      const res = await queryRag(text);
      const answer = res.answer || res.response || "";
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
      
      // Update chat history
      state.chatHistory[state.chatHistory.length - 1] = {
        role: "assistant",
        text: answer,
        meta: sourceMeta,
        timestamp: new Date().toISOString()
      };
      saveChatHistory();
    } catch (err) {
      if (err.name === 'AbortError') {
        // Request was cancelled
        const messagesEl = el("messages");
        const thinking = messagesEl.lastChild;
        const content = thinking.querySelector(".msg__content");
        if (content) {
          content.textContent = "Request cancelled";
          content.style.fontStyle = "italic";
          content.style.color = "var(--text-light)";
        }
      } else {
        addMessage("assistant", `Error: ${err.message}`);
      }
    } finally {
      // Always restore send button
      sendBtn.style.display = "flex";
      stopBtn.style.display = "none";
      state.currentAbortController = null;
    }
  });

  // Stop button handler
  const stopBtn = el("stopBtn");
  if (stopBtn) {
    stopBtn.addEventListener("click", (e) => {
      e.preventDefault();
      if (state.currentAbortController) {
        state.currentAbortController.abort();
        console.log("Request cancelled by user");
      }
    });
  }

  // Auto-resize textarea
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + "px";
  });

  // Documentation modal
  const documentationBtn = el("documentationBtn");
  const closeDocumentationBtn = el("closeDocumentationBtn");
  const tabRetrievalGuide = el("tabRetrievalGuide");
  const tabImplementation = el("tabImplementation");

  if (documentationBtn) {
    documentationBtn.addEventListener("click", async () => {
      openModal("documentationModal");
      await loadDocumentation("retrieval-guide");
    });
  }

  if (closeDocumentationBtn) {
    closeDocumentationBtn.addEventListener("click", () => {
      closeModal("documentationModal");
    });
  }

  if (tabRetrievalGuide) {
    tabRetrievalGuide.addEventListener("click", async () => {
      setActiveTab("retrieval-guide");
      await loadDocumentation("retrieval-guide");
    });
  }

  if (tabImplementation) {
    tabImplementation.addEventListener("click", async () => {
      setActiveTab("implementation");
      await loadDocumentation("implementation");
    });
  }
}

function setActiveTab(tabName) {
  const tabs = document.querySelectorAll(".docs-tab");
  tabs.forEach(tab => {
    tab.classList.remove("docs-tab--active");
  });
  
  if (tabName === "retrieval-guide") {
    el("tabRetrievalGuide").classList.add("docs-tab--active");
  } else if (tabName === "implementation") {
    el("tabImplementation").classList.add("docs-tab--active");
  }
}

async function loadDocumentation(docType) {
  const docsContent = el("docsContent");
  if (!docsContent) return;

  docsContent.innerHTML = '<div class="loading">Loading documentation...</div>';

  try {
    const response = await fetch(`/documentation/${docType}`);
    if (!response.ok) {
      throw new Error(`Failed to load documentation: ${response.statusText}`);
    }
    
    const html = await response.text();
    docsContent.innerHTML = html;
  } catch (err) {
    docsContent.innerHTML = `<div class="loading" style="color: #e74c3c;">Error loading documentation: ${err.message}</div>`;
  }
}

(async function init() {
  try {
    setActiveCollection("");
    wireEvents();
    
    // Load collections (non-blocking)
    loadCollections().catch(e => {
      console.error("Failed to load collections:", e);
    });
    
    // Load custom profiles (non-blocking)
    loadCustomProfiles().catch(e => {
      console.error("Failed to load custom profiles:", e);
    });
    
    // Load chat sessions (non-blocking)
    loadChatSessions().catch(e => {
      console.error("Failed to load chat sessions:", e);
    });
    
    // Load chat history from localStorage (synchronous)
    try {
      loadChatHistory();
    } catch (e) {
      console.error("Failed to load chat history:", e);
    }
    
    // Initialize retrieval controls
    updateProfileDescription(state.retrievalProfile);
    updateWeightDisplays();
    
    console.log("App initialized successfully");
  } catch (e) {
    console.error("Critical error during initialization:", e);
    alert("Failed to initialize app. Please refresh the page.");
  }
})();
