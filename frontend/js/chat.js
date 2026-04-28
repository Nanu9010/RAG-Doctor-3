/**
 * MedRAG – Chat & Dashboard Controller
 * Handles: query flow, message rendering, confidence ring,
 *          source cards, hallucination banner, history,
 *          documents, analytics, sidebar, panel routing.
 */

/* ══════════════════════════════════════════════════════════════════════════
   PANEL NAVIGATION
══════════════════════════════════════════════════════════════════════════ */
function switchPanel(name) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const panel = document.getElementById(`panel-${name}`);
  if (panel) panel.classList.add("active");

  const navItem = document.querySelector(`.nav-item[data-panel="${name}"]`);
  if (navItem) navItem.classList.add("active");

  // Lazy-load panel data
  if (name === "history")   loadHistory();
  if (name === "documents") loadDocuments();
  if (name === "stats")     loadStats();
}

/* Sidebar collapse */
document.getElementById("sidebarToggle")?.addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("collapsed");
});

/* ══════════════════════════════════════════════════════════════════════════
   CHAT – INPUT
══════════════════════════════════════════════════════════════════════════ */
function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

function handleInputKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    sendQuery();
  }
}

function fillExample(btn) {
  const input = document.getElementById("queryInput");
  input.value = btn.textContent;
  autoResize(input);
  input.focus();
}

function clearChat() {
  const msgs = document.getElementById("chatMessages");
  msgs.innerHTML = `<div class="chat-welcome" id="chatWelcome">
    <div class="welcome-icon">
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="20" r="18" stroke="var(--teal)" stroke-width="1.5" opacity="0.4"/>
        <path d="M14 20h12M20 14v12" stroke="var(--teal)" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </div>
    <h3>Ready for Clinical Queries</h3>
    <p>Ask questions grounded in your uploaded medical literature.</p>
    <div class="welcome-examples">
      <button class="example-chip" onclick="fillExample(this)">First-line treatment for hypertension?</button>
      <button class="example-chip" onclick="fillExample(this)">Diagnosis criteria for Type 2 Diabetes?</button>
      <button class="example-chip" onclick="fillExample(this)">ACLS protocol for ventricular fibrillation?</button>
      <button class="example-chip" onclick="fillExample(this)">Antibiotic choice for community-acquired pneumonia?</button>
    </div>
  </div>`;

  // Reset sources + confidence
  document.getElementById("sourcesList").innerHTML = `<div class="sources-empty">Sources will appear here after your first query.</div>`;
  document.getElementById("sourcesCount").textContent = "0";
  document.getElementById("confidenceSection").style.display = "none";
  document.getElementById("hallucinationBanner").style.display = "none";
}

/* ══════════════════════════════════════════════════════════════════════════
   CHAT – QUERY FLOW
══════════════════════════════════════════════════════════════════════════ */
async function sendQuery() {
  const input    = document.getElementById("queryInput");
  const question = input.value.trim();
  if (!question) return;

  const sendBtn = document.getElementById("sendBtn");
  sendBtn.disabled = true;
  input.value = "";
  autoResize(input);

  // Hide welcome
  document.getElementById("chatWelcome")?.remove();

  // Hide hallucination banner
  document.getElementById("hallucinationBanner").style.display = "none";

  appendMessage(question, "user");
  showTypingIndicator();

  const specialty = document.getElementById("specialtyFilter")?.value || "";

  try {
    const result = await apiPost("/rag/query/", {
      question,
      specialty_filter: specialty || undefined,
      top_k: 5,
    });

    removeTypingIndicator();
    appendBotMessage(result);
    updateSourcesPanel(result.sources || []);
    updateConfidenceRing(result);
    updateHallucinationBanner(result);

  } catch (err) {
    removeTypingIndicator();
    showToast(err.message || "Query failed.", "error");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   MESSAGE RENDERING
══════════════════════════════════════════════════════════════════════════ */
function appendMessage(text, role) {
  const msgs = document.getElementById("chatMessages");
  document.getElementById("chatWelcome")?.remove();

  const div = document.createElement("div");
  div.className = `message msg-${role}`;
  div.innerHTML = `<div class="msg-bubble">${role === "user" ? escapeHtml(text) : renderMarkdown(text)}</div>
    <div class="msg-meta"><span class="msg-time">${_now()}</span></div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function appendBotMessage(result) {
  const msgs = document.getElementById("chatMessages");
  const isRisk = result.is_hallucination_risk;
  const label  = result.confidence_label || "medium";
  const pct    = Math.round((result.confidence_score || 0) * 100);

  const div = document.createElement("div");
  div.className = "message msg-bot";

  // Sources inline
  let sourcesHtml = "";
  if (result.sources && result.sources.length > 0) {
    const tags = result.sources.slice(0, 4).map(s =>
      `<div class="msg-source-tag">
        <div class="msg-source-dot"></div>
        <span>${escapeHtml(s.source || s.title || "Unknown")} (${s.speciality || ""}${s.date ? " · " + s.date : ""})</span>
       </div>`
    ).join("");
    sourcesHtml = `<div class="msg-sources">${tags}</div>`;
  }

  div.innerHTML = `
    <div class="msg-bubble ${isRisk ? "msg-hallucination-warning" : ""}">
      ${renderMarkdown(result.answer)}
      ${sourcesHtml}
    </div>
    <div class="msg-meta">
      <span class="msg-time">${_now()}</span>
      <span class="msg-badge badge-${label}">${label.toUpperCase()} · ${pct}%</span>
      ${isRisk ? '<span class="msg-badge badge-critical">⚠ RISK</span>' : ""}
      <span style="color:var(--text-dim); font-size:0.65rem;">${result.response_time_ms}ms · ${result.chunks_retrieved || 0} chunks</span>
    </div>`;

  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;

  // Save query_id if returned (for feedback)
  if (result.query_id) div.dataset.queryId = result.query_id;
}

/* Typing indicator */
function showTypingIndicator() {
  const msgs = document.getElementById("chatMessages");
  const div  = document.createElement("div");
  div.className = "message msg-bot";
  div.id = "typingIndicator";
  div.innerHTML = `<div class="typing-indicator">
    <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
  </div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}
function removeTypingIndicator() {
  document.getElementById("typingIndicator")?.remove();
}

/* ══════════════════════════════════════════════════════════════════════════
   SOURCES PANEL + CONFIDENCE RING
══════════════════════════════════════════════════════════════════════════ */
function updateSourcesPanel(sources) {
  const list  = document.getElementById("sourcesList");
  const count = document.getElementById("sourcesCount");
  count.textContent = sources.length;

  if (!sources.length) {
    list.innerHTML = `<div class="sources-empty">No sources were retrieved for this query.</div>`;
    return;
  }

  list.innerHTML = sources.map((s, i) => {
    const scorePct = Math.round((s.score || 0) * 100);
    return `<div class="source-card" style="animation-delay:${i * 0.05}s">
      <div class="source-card-title">${escapeHtml(s.title || s.source || "Document")}</div>
      <div class="source-card-meta">
        <span class="source-tag teal">${escapeHtml(s.speciality || "general")}</span>
        <span class="source-tag">${escapeHtml(s.date || "—")}</span>
        <span class="source-tag">${escapeHtml(s.source || "")}</span>
      </div>
      <div class="source-score">
        <div class="source-score-bar">
          <div class="source-score-fill" style="width:${scorePct}%"></div>
        </div>
        <span class="source-score-val">${scorePct}%</span>
      </div>
    </div>`;
  }).join("");
}

function updateConfidenceRing(result) {
  const section = document.getElementById("confidenceSection");
  section.style.display = "block";

  const score = result.confidence_score || 0;
  const pct   = Math.round(score * 100);
  const label = result.confidence_label || "medium";

  // Ring animation: circumference = 2π×32 ≈ 201
  const arc    = document.getElementById("confidenceArc");
  const pctEl  = document.getElementById("confidencePct");
  const lblEl  = document.getElementById("confidenceLabel");

  const strokeColor =
    label === "high"     ? "var(--success)" :
    label === "medium"   ? "var(--teal)"    :
    label === "low"      ? "var(--amber)"   : "var(--danger)";

  arc.style.stroke = strokeColor;
  arc.style.strokeDashoffset = String(201 - (201 * score));
  pctEl.style.color = strokeColor;
  pctEl.textContent = `${pct}%`;
  lblEl.textContent = label.toUpperCase();

  // Sentence grounding bars
  const barsEl = document.getElementById("groundingBars");
  if (result.sentence_grounding && result.sentence_grounding.length) {
    barsEl.innerHTML = result.sentence_grounding.slice(0, 6).map(g =>
      `<div class="grounding-row ${g.grounded ? "grounded-yes" : "grounded-no"}">
        <div class="grounding-dot"></div>
        <span class="grounding-sent">${escapeHtml(g.sentence.slice(0, 50))}…</span>
       </div>`
    ).join("");
  }
}

function updateHallucinationBanner(result) {
  const banner = document.getElementById("hallucinationBanner");
  const text   = document.getElementById("hallucinationText");
  if (result.warning_message) {
    text.textContent  = result.warning_message;
    banner.style.display = "flex";
  } else {
    banner.style.display = "none";
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   HISTORY PANEL
══════════════════════════════════════════════════════════════════════════ */
async function loadHistory() {
  const list      = document.getElementById("historyList");
  const specialty = document.getElementById("historyFilter")?.value || "";
  list.innerHTML  = `<div class="loading-state"><div class="spinner"></div><span>Loading…</span></div>`;

  try {
    const url  = specialty ? `/auth/history/?specialty=${specialty}` : "/auth/history/";
    const data = await apiGet(url);
    const items = data.results || data;

    if (!items.length) {
      list.innerHTML = `<div class="loading-state" style="color:var(--text-dim)">No queries yet.</div>`;
      return;
    }

    list.innerHTML = items.map(q => {
      const label = q.confidence_label ||
        (q.confidence_score >= 0.85 ? "high" : q.confidence_score >= 0.65 ? "medium" : "low");
      const pct   = Math.round((q.confidence_score || 0) * 100);
      return `<div class="history-card" data-id="${q.id}">
        <div class="history-card-header">
          <div class="history-query">${escapeHtml(q.query)}</div>
          <div class="history-badge">
            <span class="msg-badge badge-${label}">${label} ${pct}%</span>
            ${q.is_hallucination_risk ? '<span class="risk-pill">⚠ RISK</span>' : ""}
          </div>
        </div>
        <div class="history-answer">${escapeHtml(q.answer)}</div>
        <div class="history-footer">
          <span>${formatDate(q.created_at)}</span>
          <span>${q.speciality_filter || "all"}</span>
          <span>${q.response_time_ms}ms</span>
          <div class="feedback-btns">
            <button class="btn-feedback ${q.feedback === "helpful" ? "active-helpful" : ""}"
              onclick="submitFeedback('${q.id}', 'helpful', this)">👍</button>
            <button class="btn-feedback ${q.feedback === "unhelpful" ? "active-unhelpful" : ""}"
              onclick="submitFeedback('${q.id}', 'unhelpful', this)">👎</button>
          </div>
        </div>
      </div>`;
    }).join("");

  } catch (err) {
    list.innerHTML = `<div class="loading-state" style="color:var(--danger)">${err.message}</div>`;
  }
}

async function submitFeedback(queryId, value, btnEl) {
  try {
    await apiPatch(`/auth/history/${queryId}/feedback/`, { feedback: value });
    // Update UI
    const card  = btnEl.closest(".history-card");
    card.querySelectorAll(".btn-feedback").forEach(b => {
      b.classList.remove("active-helpful", "active-unhelpful");
    });
    btnEl.classList.add(value === "helpful" ? "active-helpful" : "active-unhelpful");
    showToast("Feedback recorded. Thank you!", "success");
  } catch {
    showToast("Could not save feedback.", "error");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   DOCUMENTS PANEL
══════════════════════════════════════════════════════════════════════════ */
let _pendingFile = null;

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  _pendingFile = file;

  const preview = document.getElementById("uploadPreview");
  preview.textContent = `📄 ${file.name}  (${(file.size / 1024).toFixed(1)} KB)`;

  document.getElementById("docTitle").value = file.name.replace(/\.[^.]+$/, "");
  document.getElementById("uploadForm").style.display = "block";
  document.getElementById("uploadForm").scrollIntoView({ behavior: "smooth" });
}

function cancelUpload() {
  _pendingFile = null;
  document.getElementById("uploadForm").style.display = "none";
  document.getElementById("fileInput").value = "";
}

async function submitUpload() {
  if (!_pendingFile) return;

  const fd = new FormData();
  fd.append("file",             _pendingFile);
  fd.append("title",            document.getElementById("docTitle").value || _pendingFile.name);
  fd.append("specialty",        document.getElementById("docSpecialty").value);
  fd.append("source",           document.getElementById("docSource").value);
  fd.append("publication_date", document.getElementById("docYear").value);

  try {
    await apiUpload("/documents/", fd);
    cancelUpload();
    showToast("Document uploaded and indexing started!", "success");
    loadDocuments();
  } catch (err) {
    showToast(err.message || "Upload failed.", "error");
  }
}

async function loadDocuments() {
  const list = document.getElementById("docList");
  list.innerHTML = `<div class="loading-state"><div class="spinner"></div><span>Loading…</span></div>`;

  try {
    const data  = await apiGet("/documents/");
    const items = data.results || data;

    if (!items.length) {
      list.innerHTML = `<div class="loading-state" style="color:var(--text-dim);grid-column:1/-1">No documents uploaded yet.</div>`;
      return;
    }

    list.innerHTML = items.map((d, i) => `
      <div class="doc-card" style="animation-delay:${i * 0.04}s">
        <div class="doc-card-header">
          <div class="doc-title">${escapeHtml(d.title)}</div>
          <span class="doc-status status-${d.status}">${d.status}</span>
        </div>
        <div class="doc-meta">
          <span class="source-tag teal">${escapeHtml(d.specialty)}</span>
          <span class="source-tag">${escapeHtml(d.file_type?.toUpperCase() || "")}</span>
          ${d.source ? `<span class="source-tag">${escapeHtml(d.source)}</span>` : ""}
        </div>
        <div class="doc-footer">
          <span>${d.chunk_count} chunks</span>
          <span>${formatDate(d.created_at)}</span>
          <button class="btn-doc-delete" onclick="deleteDocument('${d.id}', this)">🗑 Delete</button>
        </div>
        ${d.status === "failed" ? `<div style="color:var(--danger);font-size:0.72rem;margin-top:6px;">${escapeHtml(d.error_message || "")}</div>` : ""}
      </div>`).join("");

    // Poll for processing docs
    if (items.some(d => d.status === "processing" || d.status === "pending")) {
      setTimeout(loadDocuments, 5000);
    }

  } catch (err) {
    list.innerHTML = `<div class="loading-state" style="color:var(--danger);grid-column:1/-1">${err.message}</div>`;
  }
}

async function deleteDocument(id, btnEl) {
  if (!confirm("Delete this document and all its vectors?")) return;
  try {
    await apiDelete(`/documents/${id}/`);
    btnEl.closest(".doc-card").remove();
    showToast("Document deleted.", "success");
  } catch (err) {
    showToast(err.message || "Delete failed.", "error");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   ANALYTICS PANEL
══════════════════════════════════════════════════════════════════════════ */
async function loadStats() {
  const grid = document.getElementById("statsGrid");
  grid.innerHTML = `<div class="loading-state" style="grid-column:1/-1"><div class="spinner"></div><span>Loading…</span></div>`;

  try {
    const [stats, collection] = await Promise.all([
      apiGet("/auth/stats/"),
      apiGet("/rag/collection/stats/").catch(() => ({ vectors_count: "—", status: "—" })),
    ]);

    const cards = [
      { label: "Total Queries",        value: stats.total_queries,       sub: "Lifetime queries" },
      { label: "Avg. Confidence",      value: `${Math.round((stats.avg_confidence || 0) * 100)}%`, sub: "Grounding quality" },
      { label: "Hallucination Flags",  value: stats.hallucination_flagged, sub: "High-risk answers" },
      { label: "Helpful Responses",    value: stats.helpful_responses,   sub: "Doctor-rated" },
      { label: "Vectors Indexed",      value: collection.vectors_count ?? "—", sub: "In Qdrant" },
      { label: "DB Status",            value: collection.status ?? "—", sub: "Qdrant collection" },
      { label: "Your Specialty",       value: (stats.specialty || "general").replace(/_/g, " "), sub: "Focus area" },
    ];

    grid.innerHTML = cards.map((c, i) => `
      <div class="stat-card" style="animation-delay:${i * 0.06}s">
        <div class="stat-label">${c.label}</div>
        <div class="stat-value">${c.value}</div>
        <div class="stat-sub">${c.sub}</div>
      </div>`).join("");

  } catch (err) {
    grid.innerHTML = `<div class="loading-state" style="grid-column:1/-1;color:var(--danger)">${err.message}</div>`;
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   UTILITIES
══════════════════════════════════════════════════════════════════════════ */
function _now() {
  return new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

/* ── Init ─────────────────────────────────────────────────────────────── */
document.getElementById("queryInput")?.addEventListener("keydown", handleInputKeydown);
