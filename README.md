# 🧘‍♂️ YogaFlex

YogaFlex is a real-time yoga posture detection and feedback system designed to help users improve their alignment and stability while performing yoga poses. It leverages computer vision and pose estimation techniques to analyze body posture and provide instant corrective feedback.

Unlike basic pose detection systems, YogaFlex focuses on angle-based analysis and real-time feedback delivery, making it more interactive and user-centric.

---

## 📌 Overview

YogaFlex works by capturing live video input from a webcam and processing each frame to detect human body landmarks. These landmarks are then used to calculate joint angles and compare them with predefined ideal pose configurations.

The system provides:

- Live visual feedback
- Similarity scoring
- Pose correction suggestions
- Rep counting and hold duration tracking
- Personalized session recommendations based on performance history

This makes it useful for beginners and intermediate users practicing yoga without a trainer.

---

## ✨ Key Features

**Real-Time Pose Detection**
Processes live webcam feed using OpenCV

**Angle-Based Pose Evaluation**
Calculates joint angles and compares with ideal values

**Multiple Pose Support**
- T Pose
- Triangle Pose
- Tree Pose
- Mountain Pose
- Crescent Lunge Pose
- Warrior Pose
- Bridge Pose
- Cat-Cow Pose
- Cobra Pose
- Downward Dog
- Lotus Pose
- Pigeon Pose
- Seated Forward Bend
- Standing Forward Fold
- Legs Up The Wall

**Instant Feedback System**
- Displays similarity score
- Highlights incorrect posture
- Suggests corrections
- Color-coded skeleton overlay (green / orange / red)

**Rep Counter**
- Automatically counts completed pose reps
- Tracks hold duration per rep
- State-aware detection (entering / holding / exiting)

**Session Persistence**
- Stores pose attempts and scores across sessions
- Tracks average and peak similarity per pose

**Adaptive Difficulty**
- Clusters historical performance into weak / moderate / strong groups
- Recommends a personalized pose sequence for the next session
- Identifies poses that need the most attention

**WebSocket Communication**
Enables real-time interaction between backend and frontend

**Voice Feedback**
Spoken corrections delivered hands-free during practice

---

## 🛠 Tech Stack

- **Language:** Python
- **Backend:** FastAPI
- **Computer Vision:** OpenCV
- **Pose Estimation:** MediaPipe
- **Data Processing:** NumPy
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript

---

## 📁 Project Structure

```
YogaFlex/
├── api/
│   └── main.py                      # FastAPI backend & WebSocket handling
├── logic/
│   ├── T_pose.py
│   ├── traingle_pose.py
│   ├── Tree_pose.py
│   ├── Crescent_lunge_pose.py
│   ├── warrior_pose.py
│   ├── mountain_pose.py
│   ├── bridge_pose.py
│   ├── cat_pose.py
│   ├── cobra_pose.py
│   ├── downward_dog_pose.py
│   ├── legs_wall_pose.py
│   ├── pigeon_pose.py
│   ├── lotus_pose.py
│   ├── seated_forward_bent.py
│   ├── standing_forward_bent_pose.py
│   ├── rep_counter.py               # Rep counting via state machine
│   ├── session_store.py             # SQLite session persistence
│   └── difficulty_adapter.py        # K-Means performance clustering
├── tests/
│   ├── index.html                   # Frontend interface
│   ├── script.js
│   └── style.css
├── yogaflex.db                      # Auto-generated on first run
└── README.md
```

---

## ⚙️ How It Works

**Video Capture**
The system accesses the webcam using OpenCV.

**Pose Detection**
MediaPipe extracts body landmarks from each frame.

**Angle Calculation**
Joint angles are computed using geometric formulas.

**Comparison with Ideal Pose**
Angles are compared with predefined thresholds.

**Feedback Generation**
- Similarity score is calculated
- Corrections are generated per joint
- Annotated frame is returned with color-coded skeleton

**Rep & Hold Tracking**
A state machine monitors the similarity score stream to detect completed reps and measure hold durations automatically.

**Session Recording**
Each pose attempt is logged to a local SQLite database with similarity scores, rep count, and hold duration.

**Adaptive Recommendations**
After sufficient sessions, K-Means clustering groups poses by performance level and generates a personalized practice sequence targeting weak areas.

**Real-Time Communication**
All data is sent to the frontend via WebSockets.

---

## 🔌 API Endpoints

**WebSocket**
- `WS /ws/{client_id}` — streams processed frames and feedback

**REST**
- `GET /health` — server liveness check
- `GET /adapt` — returns performance clusters and next session recommendation
- `GET /session/{session_id}/summary` — aggregated stats for a completed session

---

## ▶️ Running the Project

**1. Clone Repository**
```bash
git clone https://github.com/your-username/YogaFlex.git
cd YogaFlex
```

**2. Install Dependencies**
```bash
pip install -r requirements.txt
```

**3. Run Backend**
```bash
uvicorn api.main:app --reload
```

**4. Open Frontend**
Open `tests/index.html` in your browser

---

## ⚠️ Important Notes

- Requires a local machine with webcam
- Not suitable for cloud deployment without hardware access
- Works best in good lighting conditions
- Session data and performance history are stored in `yogaflex.db` at the project root
- Adaptive recommendations activate after 10 or more pose attempts are logged

---

## 🚀 Future Improvements

- Improve UI with React
- Optimize performance using multithreading
- Deploy using client-side camera processing
- Add multi-user profile support
- Extend voice feedback with guided session narration

---

## 🎯 Contribution

This project focuses on:

- Designing pose evaluation logic
- Implementing angle-based comparison
- Building real-time feedback system
- Developing adaptive training intelligence

---

## 📜 License

This project is intended for educational purposes.
