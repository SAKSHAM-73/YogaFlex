from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import cv2
import time
import sys
import os
import json
import base64
import asyncio
from typing import Dict, Optional

from fastapi.middleware.cors import CORSMiddleware

# Import logic modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logic.T_pose import TPoseAngleChecker
from logic.traingle_pose import TrianglePoseAngleChecker
from logic.Tree_pose import TreePoseAngleChecker
from logic.Crescent_lunge_pose import CrescentLungeAngleChecker
from logic.warrior_pose import WarriorPoseAngleChecker
from logic.mountain_pose import MountainPoseAngleChecker
from logic.bridge_pose import BridgePoseAngleChecker
from logic.cat_pose import CatCowPoseAngleChecker
from logic.cobra_pose import CobraPoseAngleChecker
from logic.downward_dog_pose import DownwardDogPoseAngleChecker
from logic.legs_wall_pose import LegsUpTheWallPoseAngleChecker
from logic.pigeon_pose import PigeonPoseAngleChecker
from logic.lotus_pose import PadmasanDistanceAngleChecker
from logic.seated_forward_bent import SeatedForwardBendAngleChecker
from logic.standing_forward_bent_pose import StandingForwardFoldAngleChecker

# ── New ML features ─────────────────────────────────────────────────────────
from logic.rep_counter import RepCounter
from logic import session_store
from logic import difficulty_adapter
# ────────────────────────────────────────────────────────────────────────────

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise SQLite tables on startup
session_store.init_db()

# Pose mapping
pose_checkers = {
    "Triangle":          TrianglePoseAngleChecker(),
    "Tree":              TreePoseAngleChecker(),
    "T":                 TPoseAngleChecker(),
    "Crescent_lunge":    CrescentLungeAngleChecker(),
    "Warrior":           WarriorPoseAngleChecker(),
    "Mountain":          MountainPoseAngleChecker(),
    "Bridge":            BridgePoseAngleChecker(),
    "Cat-Cow":           CatCowPoseAngleChecker(),
    "Cobra":             CobraPoseAngleChecker(),
    "Seated":            SeatedForwardBendAngleChecker(),
    "Standing":          StandingForwardFoldAngleChecker(),
    "Downward Dog":      DownwardDogPoseAngleChecker(),
    "Lotus":             PadmasanDistanceAngleChecker(),
    "Pigeon":            PigeonPoseAngleChecker(),
    "Legs-Up-The-Wall":  LegsUpTheWallPoseAngleChecker(),
}


# ============================
# 🔗 CONNECTION MANAGER
# ============================

class ConnectionManager:
    def __init__(self):
        self.active_connections:  Dict[str, WebSocket]    = {}
        self.processing_tasks:    Dict[str, asyncio.Task] = {}
        self.client_delays:       Dict[str, float]        = {}
        self.last_feedback_time:  Dict[str, float]        = {}

        # ── Per-client state for new features ──────────────────────────────
        self.rep_counters:   Dict[str, RepCounter]    = {}   # live rep counters
        self.session_ids:    Dict[str, int]           = {}   # DB session IDs
        # Accumulate similarity readings to persist at session end
        self._sim_buffer:    Dict[str, list[float]]   = {}
        self._peak_sim:      Dict[str, float]         = {}
        self._current_pose:  Dict[str, str]           = {}
        # ───────────────────────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

        # Open a new DB session
        sid = session_store.start_session(client_id)
        self.session_ids[client_id]  = sid
        self.rep_counters[client_id] = RepCounter()
        self._sim_buffer[client_id]  = []
        self._peak_sim[client_id]    = 0.0
        self._current_pose[client_id] = ""

    def disconnect(self, client_id: str):
        # ── Flush buffered pose stats to DB before closing ─────────────────
        self._flush_pose_log(client_id)

        sid = self.session_ids.pop(client_id, None)
        if sid:
            session_store.end_session(sid)

        # Cancel the processing task BEFORE clearing the dict
        task = self.processing_tasks.pop(client_id, None)
        if task:
            task.cancel()

        for store in (
            self.active_connections,
            self.client_delays, self.last_feedback_time,
            self.rep_counters, self._sim_buffer,
            self._peak_sim, self._current_pose,
        ):
            store.pop(client_id, None)

    def _flush_pose_log(self, client_id: str):
        """Persist the current pose buffer to SQLite."""
        sims = self._sim_buffer.get(client_id, [])
        pose = self._current_pose.get(client_id, "")
        sid  = self.session_ids.get(client_id)
        rc   = self.rep_counters.get(client_id)

        if not sims or not pose or not sid:
            return

        avg_sim  = sum(sims) / len(sims)
        peak_sim = self._peak_sim.get(client_id, 0.0)
        reps     = rc.reps if rc else 0
        hold_sec = rc._hold_sec if rc else 0.0

        session_store.log_pose_attempt(
            session_id      = sid,
            pose_name       = pose,
            avg_similarity  = avg_sim,
            peak_similarity = peak_sim,
            reps            = reps,
            hold_sec        = hold_sec,
        )

        # Reset buffer for next pose
        self._sim_buffer[client_id]  = []
        self._peak_sim[client_id]    = 0.0

    async def start_processing(self, client_id: str, pose_type: str):
        # Flush previous pose before switching
        self._flush_pose_log(client_id)

        # Reset rep counter for new pose
        if client_id in self.rep_counters:
            self.rep_counters[client_id].reset()

        self._current_pose[client_id] = pose_type

        if client_id in self.processing_tasks:
            self.processing_tasks[client_id].cancel()

        task = asyncio.create_task(self.process_frames(client_id, pose_type))
        self.processing_tasks[client_id] = task


# ============================
# 🎥 FRAME PROCESSING
# ============================

    async def process_frames(self, client_id: str, pose_type: str):
        if client_id not in self.active_connections:
            return

        websocket = self.active_connections[client_id]
        checker   = pose_checkers.get(pose_type, TPoseAngleChecker())
        counter   = self.rep_counters[client_id]

        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 15)
        if not cap.isOpened():
            await websocket.send_json({"error": "Could not open webcam"})
            return

        try:
            while client_id in self.active_connections:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.01)
                    continue

                frame = cv2.flip(frame, 1)

                user_keypoints, landmarks = checker.process_frame(frame)

                if user_keypoints is None:
                    overall_sim   = 0.0
                    joint_sims    = {}
                    feedback_text = "No pose detected."
                    rep_data      = counter.update(0.0)
                else:
                    overall_sim, joint_sims = checker.compute_pose_similarity(user_keypoints)
                    feedback_lines = checker.generate_feedback(overall_sim, joint_sims)
                    feedback_text  = f"Similarity: {overall_sim*100:.2f}%\n" + "\n".join(feedback_lines)

                    # ── Rep counter update ────────────────────────────────
                    rep_data = counter.update(overall_sim)

                    # ── Accumulate similarity for DB flush ────────────────
                    self._sim_buffer[client_id].append(overall_sim)
                    if overall_sim > self._peak_sim.get(client_id, 0.0):
                        self._peak_sim[client_id] = overall_sim

                    # 🎨 Visual overlay
                    frame = default_annotate(frame, landmarks, checker, joint_sims)

                # Encode frame
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                # Feedback throttle
                current_time = time.time()
                delay        = self.client_delays.get(client_id, 0.7)
                last_time    = self.last_feedback_time.get(client_id, 0)
                send_feedback = (current_time - last_time) > delay

                if send_feedback:
                    self.last_feedback_time[client_id] = current_time

                data: dict = {"frame": frame_base64}

                if send_feedback:
                    data["feedback"] = {
                        "similarity":        float(overall_sim),
                        "feedback_text":     feedback_text,
                        "joint_similarities": joint_sims,
                        # ── Rep counter payload ───────────────────────────
                        "rep_data": {
                            "reps":       rep_data["reps"],
                            "hold_sec":   rep_data["hold_sec"],
                            "last_hold":  rep_data["last_hold"],
                            "state":      rep_data["state"],
                        },
                    }

                await websocket.send_json(data)
                await asyncio.sleep(0.03)

        except Exception as e:
            print(f"[process_frames] {e}")

        finally:
            cap.release()


# ============================
# 🎨 VISUAL FEEDBACK OVERLAY
# ============================

def default_annotate(frame, landmarks, checker, joint_sims=None):
    if landmarks is not None:
        import mediapipe as mp
        mp_drawing = mp.solutions.drawing_utils
        mp_pose    = checker.mp_pose if hasattr(checker, "mp_pose") else mp.solutions.pose

        color = (0, 255, 0)
        if joint_sims:
            avg_sim = sum(joint_sims.values()) / len(joint_sims)
            if avg_sim < 0.7:
                color = (0, 0, 255)
            elif avg_sim < 0.9:
                color = (0, 165, 255)
            else:
                color = (0, 255, 0)

        mp_drawing.draw_landmarks(
            frame, landmarks, mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=3),
            mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=2),
        )
    return frame


# ============================
# 🌐 WEBSOCKET ENDPOINT
# ============================

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)

    try:
        while True:
            data      = await websocket.receive_text()
            json_data = json.loads(data)

            if "pose_type" in json_data:
                await manager.start_processing(client_id, json_data["pose_type"])

            elif json_data.get("command") == "stop":
                manager.disconnect(client_id)
                break

            elif json_data.get("command") == "update_delay":
                manager.client_delays[client_id] = float(json_data.get("delay", 0.7))

    except WebSocketDisconnect:
        manager.disconnect(client_id)


# ============================
# 📊 REST ENDPOINTS
# ============================

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/session/{session_id}/summary")
async def session_summary(session_id: int):
    """Returns aggregated stats for a completed session."""
    return session_store.get_session_summary(session_id)


@app.get("/adapt")
async def get_adaptation():
    """
    Runs K-Means clustering on all stored pose logs and returns:
    - weak_zones, strong_poses, next_session recommendation, insight text
    """
    logs   = session_store.get_all_pose_logs()
    result = difficulty_adapter.analyze(logs)
    return result
