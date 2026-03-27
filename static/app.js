const el = (id) => document.getElementById(id);

const state = {
  collection: "",
  chatHistory: [],
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

function openEditView(collection) {
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
    clearChatHistory();
  });

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
      
      // Update chat history
      state.chatHistory[state.chatHistory.length - 1] = {
        role: "assistant",
        text: answer,
        meta: sourceMeta,
        timestamp: new Date().toISOString()
      };
      saveChatHistory();
    } catch (err) {
      addMessage("assistant", `Error: ${err.message}`);
    }
  });

  // Auto-resize textarea
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + "px";
  });
}

(async function init() {
  setActiveCollection("");
  wireEvents();
  await loadCollections();
  loadChatHistory();
})();
