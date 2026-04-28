/**
 * MedRAG – Voice AI Module
 * Records audio via MediaRecorder API → uploads to /rag/voice/query/
 * Plays TTS response back via <audio> element.
 */

let _mediaRecorder = null;
let _audioChunks   = [];
let _isRecording   = false;
let _stream        = null;

/* ── Toggle Recording ───────────────────────────────────────────────────── */
async function toggleVoice() {
  if (_isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    _stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    showToast("Microphone access denied.", "error");
    return;
  }

  _audioChunks = [];
  _mediaRecorder = new MediaRecorder(_stream, { mimeType: "audio/webm;codecs=opus" });

  _mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) _audioChunks.push(e.data);
  };

  _mediaRecorder.onstop = async () => {
    const blob = new Blob(_audioChunks, { type: "audio/webm" });
    await _submitVoiceQuery(blob);
  };

  _mediaRecorder.start(200);  // collect in 200ms chunks
  _isRecording = true;
  _updateVoiceUI(true);
  showToast("Recording… click mic again to stop.", "info", 60000);
}

function stopRecording() {
  if (_mediaRecorder && _mediaRecorder.state !== "inactive") {
    _mediaRecorder.stop();
  }
  if (_stream) {
    _stream.getTracks().forEach(t => t.stop());
    _stream = null;
  }
  _isRecording = false;
  _updateVoiceUI(false);
  // Dismiss any lingering info toast
  document.querySelectorAll(".toast-info").forEach(t => t.remove());
}

function _updateVoiceUI(recording) {
  const btn    = document.getElementById("voiceBtn");
  const waves  = document.getElementById("voiceWaves");
  const icon   = btn?.querySelector(".voice-icon");

  if (!btn) return;
  btn.classList.toggle("recording", recording);
  if (waves) waves.style.display = recording ? "flex" : "none";
  if (icon)  icon.style.display  = recording ? "none" : "block";
}

/* ── Submit Voice Query ─────────────────────────────────────────────────── */
async function _submitVoiceQuery(audioBlob) {
  const sendBtn = document.getElementById("sendBtn");
  if (sendBtn) sendBtn.disabled = true;

  // Show typing indicator
  showTypingIndicator();

  const specialty = document.getElementById("specialtyFilter")?.value || "";
  const formData  = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  if (specialty) formData.append("specialty_filter", specialty);

  try {
    const data = await apiUpload("/rag/voice/query/", formData);

    removeTypingIndicator();

    // Show transcript as user message
    appendMessage(data.transcript, "user");

    // Show RAG result
    appendBotMessage(data.rag_result);

    // Play TTS audio if available
    if (data.audio_url) {
      _playTTS(data.audio_url);
    }

  } catch (err) {
    removeTypingIndicator();
    showToast(err.message || "Voice query failed.", "error");
  } finally {
    if (sendBtn) sendBtn.disabled = false;
  }
}

function _playTTS(audioUrl) {
  const player = document.getElementById("ttsAudio");
  if (!player) return;
  const base = window.location.protocol + "//" + window.location.hostname + ":8000";
  player.src = audioUrl.startsWith("http") ? audioUrl : base + audioUrl;
  player.play().catch(() => {});
  showToast("Playing audio response.", "info", 3000);
}

/* ── Expose for chat.js ─────────────────────────────────────────────────── */
// appendMessage and appendBotMessage are defined in chat.js
// We reference them by name; they'll be available since chat.js loads after voice.js
