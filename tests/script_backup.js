let ws;
const video = document.getElementById("video");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const feedbackBox = document.getElementById("feedback-content");

// ============================
// 🎤 VOICE ASSISTANT
// ============================

function speak(text) {
    window.speechSynthesis.cancel(); // prevent overlap
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "en-US";
    speech.rate = 0.95;
    speech.pitch = 1;
    window.speechSynthesis.speak(speech);
}

let lastSpoken = "";

function speakOnce(text) {
    if (text !== lastSpoken) {
        speak(text);
        lastSpoken = text;
    }
}


// ============================
// ⏱ SESSION TIMER
// ============================

let startTime = null;
let timerInterval = null;

function updateTimer() {
    let elapsed = Math.floor((Date.now() - startTime) / 1000);
    document.getElementById("timer").innerText = "Session: " + elapsed + " sec";
}

function startTimer() {
    resetTimer(); // ensure fresh start
    startTime = Date.now();
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

        if (document.body.classList.contains("light-mode")) {
            localStorage.setItem("theme", "light");
        } else {
            localStorage.setItem("theme", "dark");
        }
    });
}

window.onload = () => {
    if (localStorage.getItem("theme") === "light") {
        document.body.classList.add("light-mode");
    }
};


// ============================
// 🎚️ FEEDBACK DELAY CONTROL
// ============================

const feedbackDelaySelect = document.getElementById("feedbackDelay");

let feedbackDelay = parseFloat(feedbackDelaySelect ? feedbackDelaySelect.value : 0.7);

if (feedbackDelaySelect) {
  feedbackDelaySelect.addEventListener("change", () => {
    feedbackDelay = parseFloat(feedbackDelaySelect.value);

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        command: "update_delay",
        delay: feedbackDelay
      }));
    }
  });
}


// ============================
// ▶️ START BUTTON
// ============================

startBtn.addEventListener("click", () => {

  const pose = document.getElementById("poseSelect").value;
  const clientId = Date.now();

  // 🔥 START SESSION TIMER
  startTimer();
  lastSpoken = ""; 
  ws = new WebSocket(`ws://localhost:8000/ws/${clientId}`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ pose_type: pose }));

    ws.send(JSON.stringify({
      command: "update_delay",
      delay: feedbackDelay
    }));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // 🎥 Frame display
    if (data.frame) {
      document.getElementById("welcome-message").style.display = "none";
      video.style.display = "block";
      video.src = "data:image/jpeg;base64," + data.frame;
    }

    // 📊 Feedback handling
    if (data.feedback) {

      const sim = (data.feedback.similarity * 100).toFixed(2);

      feedbackBox.innerHTML = `<strong>Similarity:</strong> ${sim}%<br>
        <strong>Feedback:</strong><br>${data.feedback.feedback_text.replace(/\n/g, "<br>")}`;

      // 🎤 SMART VOICE
      const lines = data.feedback.feedback_text.split("\n");
      if (data.feedback.feedback_text.includes("No pose detected")) {
        speakOnce("Please come into frame");
        return;
      }

const instructions = lines.slice(1);

      if (data.feedback.similarity > 0.9) {
        speakOnce("Perfect pose. Hold it.");
      } else if (instructions.length > 0) {
        const cleanText = instructions[0].replace(/_/g, " ");
        speakOnce(cleanText);
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

  // 🔥 STOP SESSION TIMER
  resetTimer();
});