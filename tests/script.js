let ws;
const video       = document.getElementById("video");
const startBtn    = document.getElementById("startBtn");
const stopBtn     = document.getElementById("stopBtn");
const feedbackBox = document.getElementById("feedback-content");


// ============================
// 🎤 VOICE ASSISTANT
// ============================

function speak(text) {
  window.speechSynthesis.cancel();
  const speech  = new SpeechSynthesisUtterance(text);
  speech.lang   = "en-US";
  speech.rate   = 0.95;
  speech.pitch  = 1;
  window.speechSynthesis.speak(speech);
}

let lastSpoken = "";
function speakOnce(text) {
  if (text !== lastSpoken) { speak(text); lastSpoken = text; }
}


// ============================
// ⏱ SESSION TIMER
// ============================

let startTime    = null;
let timerInterval = null;

function updateTimer() {
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  document.getElementById("timer").innerText = "Session: " + elapsed + " sec";
}
function startTimer() {
  resetTimer();
  startTime     = Date.now();
  timerInterval = setInterval(updateTimer, 1000);
}
function resetTimer() {
  clearInterval(timerInterval);
  startTime = null;
  document.getElementById("timer").innerText = "Session: 0 sec";
}


// ============================
// 🌙 THEME TOGGLE
// ============================

const toggleBtn = document.getElementById("themeToggle");
if (toggleBtn) {
  toggleBtn.addEventListener("click", () => {
    document.body.classList.toggle("light-mode");
    localStorage.setItem("theme",
      document.body.classList.contains("light-mode") ? "light" : "dark");
  });
}
window.addEventListener("load", () => {
  if (localStorage.getItem("theme") === "light")
    document.body.classList.add("light-mode");

  // Load adaptation data on page load
  loadAdaptationPanel();
});


// ============================
// 🎚️ FEEDBACK DELAY CONTROL
// ============================

const feedbackDelaySelect = document.getElementById("feedbackDelay");
let feedbackDelay = parseFloat(feedbackDelaySelect ? feedbackDelaySelect.value : 0.7);

if (feedbackDelaySelect) {
  feedbackDelaySelect.addEventListener("change", () => {
    feedbackDelay = parseFloat(feedbackDelaySelect.value);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ command: "update_delay", delay: feedbackDelay }));
    }
  });
}


// ============================
// 🔢 REP COUNTER UI
// ============================

/**
 * Injects the rep counter widget into the page if it doesn't already exist.
 * The widget shows: reps, hold duration, and pose state badge.
 */
function ensureRepWidget() {
  if (document.getElementById("rep-widget")) return;

  const widget = document.createElement("div");
  widget.id = "rep-widget";
  widget.innerHTML = `
    <div class="rep-widget-inner">
      <div class="rep-stat">
        <span class="rep-label">REPS</span>
        <span class="rep-value" id="rep-count">0</span>
      </div>
      <div class="rep-divider"></div>
      <div class="rep-stat">
        <span class="rep-label">HOLD</span>
        <span class="rep-value" id="rep-hold">0.0s</span>
      </div>
      <div class="rep-divider"></div>
      <div class="rep-stat">
        <span class="rep-label">STATE</span>
        <span class="rep-badge" id="rep-state">idle</span>
      </div>
    </div>
  `;

  // Inject after the video/feedback area — adapt selector to your layout
  const anchor = document.getElementById("feedback-content")?.parentElement
               || document.body;
  anchor.appendChild(widget);

  // Inject widget styles
  if (!document.getElementById("rep-widget-style")) {
    const style = document.createElement("style");
    style.id = "rep-widget-style";
    style.textContent = `
      #rep-widget {
        margin-top: 16px;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 14px;
        padding: 14px 20px;
        backdrop-filter: blur(8px);
      }
      .rep-widget-inner {
        display: flex;
        align-items: center;
        gap: 16px;
      }
      .rep-stat {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 1;
      }
      .rep-label {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: rgba(255,255,255,0.45);
        text-transform: uppercase;
      }
      .rep-value {
        font-size: 28px;
        font-weight: 800;
        color: #fff;
        line-height: 1.2;
      }
      .rep-divider {
        width: 1px;
        height: 36px;
        background: rgba(255,255,255,0.12);
      }
      .rep-badge {
        font-size: 12px;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 999px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(255,255,255,0.1);
        color: #aaa;
        transition: background 0.3s, color 0.3s;
      }
      .rep-badge.holding  { background: #22c55e22; color: #22c55e; }
      .rep-badge.entering { background: #f59e0b22; color: #f59e0b; }
      .rep-badge.exiting  { background: #ef444422; color: #ef4444; }
      .rep-badge.idle     { background: rgba(255,255,255,0.08); color: #888; }

      /* Light mode overrides */
      body.light-mode #rep-widget {
        background: rgba(0,0,0,0.04);
        border-color: rgba(0,0,0,0.1);
      }
      body.light-mode .rep-label { color: rgba(0,0,0,0.4); }
      body.light-mode .rep-value { color: #111; }
      body.light-mode .rep-divider { background: rgba(0,0,0,0.1); }
    `;
    document.head.appendChild(style);
  }
}

function updateRepWidget(repData) {
  const el = (id) => document.getElementById(id);
  if (!el("rep-count")) return;

  el("rep-count").textContent = repData.reps;
  el("rep-hold").textContent  = repData.hold_sec.toFixed(1) + "s";

  const badge = el("rep-state");
  badge.textContent  = repData.state;
  badge.className    = "rep-badge " + repData.state;

  // Voice cue when a rep is completed
  if (repData.state === "exiting" && repData.last_hold > 0) {
    speakOnce(`Rep complete. ${repData.reps} done.`);
  }
}

function resetRepWidget() {
  const el = (id) => document.getElementById(id);
  if (el("rep-count")) el("rep-count").textContent = "0";
  if (el("rep-hold"))  el("rep-hold").textContent  = "0.0s";
  if (el("rep-state")) {
    el("rep-state").textContent = "idle";
    el("rep-state").className   = "rep-badge idle";
  }
}


// ============================
// 🧠 DIFFICULTY ADAPTATION PANEL
// ============================

/**
 * Fetches /adapt from the FastAPI backend, then renders:
 *  - Weak zones  (red pills)
 *  - Strong poses (green pills)
 *  - Recommended next session sequence
 *  - Insight text
 */
async function loadAdaptationPanel() {
  let panel = document.getElementById("adapt-panel");
  if (!panel) {
    panel = document.createElement("div");
    panel.id = "adapt-panel";

    // Inject after rep widget anchor or at body end
    const anchor = document.getElementById("feedback-content")?.parentElement
                 || document.body;
    anchor.appendChild(panel);

    // Panel styles
    if (!document.getElementById("adapt-panel-style")) {
      const style = document.createElement("style");
      style.id = "adapt-panel-style";
      style.textContent = `
        #adapt-panel {
          margin-top: 20px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.10);
          border-radius: 16px;
          padding: 18px 20px;
          font-size: 13px;
        }
        #adapt-panel h3 {
          margin: 0 0 12px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: rgba(255,255,255,0.4);
        }
        .adapt-section { margin-bottom: 14px; }
        .adapt-section-label {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: rgba(255,255,255,0.35);
          margin-bottom: 6px;
        }
        .adapt-pills { display: flex; flex-wrap: wrap; gap: 6px; }
        .pill {
          font-size: 11px;
          font-weight: 600;
          padding: 4px 10px;
          border-radius: 999px;
          letter-spacing: 0.04em;
        }
        .pill-weak     { background: #ef444420; color: #ef4444; border: 1px solid #ef444440; }
        .pill-strong   { background: #22c55e20; color: #22c55e; border: 1px solid #22c55e40; }
        .pill-next     { background: rgba(255,255,255,0.08); color: #ddd; border: 1px solid rgba(255,255,255,0.12); }
        .adapt-insight {
          margin-top: 10px;
          font-size: 12px;
          line-height: 1.55;
          color: rgba(255,255,255,0.55);
          font-style: italic;
        }
        .adapt-insufficient {
          color: rgba(255,255,255,0.35);
          font-style: italic;
          font-size: 12px;
        }
        #adapt-refresh {
          margin-top: 12px;
          background: none;
          border: 1px solid rgba(255,255,255,0.18);
          border-radius: 8px;
          color: rgba(255,255,255,0.5);
          padding: 4px 12px;
          font-size: 11px;
          cursor: pointer;
          transition: border-color 0.2s, color 0.2s;
        }
        #adapt-refresh:hover { border-color: rgba(255,255,255,0.4); color: #fff; }

        /* Light mode */
        body.light-mode #adapt-panel {
          background: rgba(0,0,0,0.03);
          border-color: rgba(0,0,0,0.08);
        }
        body.light-mode #adapt-panel h3,
        body.light-mode .adapt-section-label { color: rgba(0,0,0,0.35); }
        body.light-mode .adapt-insight { color: rgba(0,0,0,0.45); }
        body.light-mode .pill-next { color: #333; background: rgba(0,0,0,0.06); border-color: rgba(0,0,0,0.12); }
        body.light-mode #adapt-refresh { border-color: rgba(0,0,0,0.2); color: rgba(0,0,0,0.45); }
        body.light-mode #adapt-refresh:hover { border-color: rgba(0,0,0,0.5); color: #000; }
      `;
      document.head.appendChild(style);
    }
  }

  panel.innerHTML = `<h3>🧠 Your Training Profile</h3><p class="adapt-insufficient">Loading…</p>`;

  try {
    const res  = await fetch("http://localhost:8000/adapt");
    const data = await res.json();
    renderAdaptPanel(panel, data);
  } catch (e) {
    panel.innerHTML = `<h3>🧠 Your Training Profile</h3>
      <p class="adapt-insufficient">Could not reach backend. Start a session first.</p>`;
  }
}

function renderAdaptPanel(panel, data) {
  if (data.status === "insufficient_data") {
    panel.innerHTML = `
      <h3>🧠 Your Training Profile</h3>
      <p class="adapt-insufficient">${data.message}</p>
      <button id="adapt-refresh" onclick="loadAdaptationPanel()">↻ Refresh</button>
    `;
    return;
  }

  const pillsHTML = (arr, cls) =>
    arr.length
      ? arr.map(p => `<span class="pill ${cls}">${p}</span>`).join("")
      : `<span class="adapt-insufficient">—</span>`;

  panel.innerHTML = `
    <h3>🧠 Your Training Profile</h3>

    <div class="adapt-section">
      <div class="adapt-section-label">⚠️ Needs Work</div>
      <div class="adapt-pills">${pillsHTML(data.weak_zones, "pill-weak")}</div>
    </div>

    <div class="adapt-section">
      <div class="adapt-section-label">✅ Strengths</div>
      <div class="adapt-pills">${pillsHTML(data.strong_poses, "pill-strong")}</div>
    </div>

    <div class="adapt-section">
      <div class="adapt-section-label">📋 Recommended Next Session</div>
      <div class="adapt-pills">${pillsHTML(data.next_session, "pill-next")}</div>
    </div>

    <p class="adapt-insight">"${data.insight}"</p>
    <button id="adapt-refresh" onclick="loadAdaptationPanel()">↻ Refresh</button>
  `;
}


// ============================
// ▶️ START BUTTON
// ============================

startBtn.addEventListener("click", () => {
  const pose     = document.getElementById("poseSelect").value;
  const clientId = Date.now();

  startTimer();
  lastSpoken = "";

  ensureRepWidget();
  resetRepWidget();

  ws = new WebSocket(`ws://localhost:8000/ws/${clientId}`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ pose_type: pose }));
    ws.send(JSON.stringify({ command: "update_delay", delay: feedbackDelay }));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    // 🎥 Frame display
    if (data.frame) {
      document.getElementById("welcome-message").style.display = "none";
      video.style.display = "block";
      video.src = "data:image/jpeg;base64," + data.frame;
    }

    // 📊 Feedback + rep counter
    if (data.feedback) {
      const sim = (data.feedback.similarity * 100).toFixed(2);

      feedbackBox.innerHTML = `
        <strong>Similarity:</strong> ${sim}%<br>
        <strong>Feedback:</strong><br>
        ${data.feedback.feedback_text.replace(/\n/g, "<br>")}
      `;

      // Rep counter widget update
      if (data.feedback.rep_data) {
        updateRepWidget(data.feedback.rep_data);
      }

      // 🎤 Voice
      const lines = data.feedback.feedback_text.split("\n");
      if (data.feedback.feedback_text.includes("No pose detected")) {
        speakOnce("Please come into frame");
        return;
      }
      const instructions = lines.slice(1);
      if (data.feedback.similarity > 0.9) {
        speakOnce("Perfect pose. Hold it.");
      } else if (instructions.length > 0) {
        speakOnce(instructions[0].replace(/_/g, " "));
      }
    }
  };

  ws.onclose = () => console.log("WebSocket closed.");
});


// ============================
// ⏹ STOP BUTTON
// ============================

stopBtn.addEventListener("click", () => {
  if (ws) {
    ws.send(JSON.stringify({ command: "stop" }));
    ws.close();
  }

  video.style.display = "none";
  feedbackBox.innerHTML = "Feedback and similarity score will appear here.";
  document.getElementById("welcome-message").style.display = "block";

  resetTimer();

  // Reload adaptation panel after session ends — new data now in DB
  setTimeout(loadAdaptationPanel, 800);
});
