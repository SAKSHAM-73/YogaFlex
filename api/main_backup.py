from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import cv2
import time
import sys
import os
import json
import base64
import asyncio
from typing import Dict

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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pose mapping
pose_checkers = {
    "Triangle": TrianglePoseAngleChecker(),
    "Tree": TreePoseAngleChecker(),
    "T": TPoseAngleChecker(),
    "Crescent_lunge": CrescentLungeAngleChecker(),
    "Warrior": WarriorPoseAngleChecker(),
    "Mountain": MountainPoseAngleChecker(),
    "Bridge": BridgePoseAngleChecker(),
    "Cat-Cow": CatCowPoseAngleChecker(),
    "Cobra": CobraPoseAngleChecker(),
    "Seated": SeatedForwardBendAngleChecker(),
    "Standing": StandingForwardFoldAngleChecker(),
    "Downward Dog": DownwardDogPoseAngleChecker(),
    "Lotus": PadmasanDistanceAngleChecker(),
    "Pigeon": PigeonPoseAngleChecker(),
    "Legs-Up-The-Wall": LegsUpTheWallPoseAngleChecker()
}


# ============================
# 🔗 CONNECTION MANAGER
# ============================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.processing_tasks = {}
        self.client_delays: Dict[str, float] = {}
        self.last_feedback_time: Dict[str, float] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        if client_id in self.processing_tasks:
            self.processing_tasks[client_id].cancel()
            del self.processing_tasks[client_id]

        if client_id in self.client_delays:
            del self.client_delays[client_id]

        if client_id in self.last_feedback_time:
            del self.last_feedback_time[client_id]

    async def start_processing(self, client_id: str, pose_type: str):
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
        checker = pose_checkers.get(pose_type, TPoseAngleChecker())

        cap = cv2.VideoCapture(0)

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
                    overall_sim = 0.0
                    joint_sims = {}
                    feedback_text = "No pose detected."
                else:
                    overall_sim, joint_sims = checker.compute_pose_similarity(user_keypoints)
                    feedback_lines = checker.generate_feedback(overall_sim, joint_sims)
                    feedback_text = f"Similarity: {overall_sim*100:.2f}%\n" + "\n".join(feedback_lines)

                    # 🎨 Apply visual overlay
                    frame = default_annotate(frame, landmarks, checker, joint_sims)

                # Encode frame
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                # 🧠 Feedback delay control (PER CLIENT)
                current_time = time.time()
                delay = self.client_delays.get(client_id, 0.7)

                last_time = self.last_feedback_time.get(client_id, 0)
                send_feedback = (current_time - last_time) > delay

                if send_feedback:
                    self.last_feedback_time[client_id] = current_time

                # Send frame always
                data = {"frame": frame_base64}

                # Send feedback occasionally
                if send_feedback:
                    data["feedback"] = {
                        "similarity": float(overall_sim),
                        "feedback_text": feedback_text,
                        "joint_similarities": joint_sims
                    }

                await websocket.send_json(data)

                await asyncio.sleep(0.03)

        except Exception as e:
            print(f"Error: {e}")

        finally:
            cap.release()


# ============================
# 🎨 VISUAL FEEDBACK OVERLAY
# ============================

def default_annotate(frame, landmarks, checker, joint_sims=None):
    if landmarks is not None:
        import mediapipe as mp
        mp_drawing = mp.solutions.drawing_utils
        mp_pose = checker.mp_pose if hasattr(checker, "mp_pose") else mp.solutions.pose

        # Default green
        color = (0, 255, 0)

        if joint_sims:
            avg_sim = sum(joint_sims.values()) / len(joint_sims)

            if avg_sim < 0.7:
                color = (0, 0, 255)       # 🔴 Red
            elif avg_sim < 0.9:
                color = (0, 165, 255)     # 🟠 Orange
            else:
                color = (0, 255, 0)       # 🟢 Green

        mp_drawing.draw_landmarks(
            frame,
            landmarks,
            mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=3),
            mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=2)
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
            data = await websocket.receive_text()
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


@app.get("/health")
async def health_check():
    return {"status": "healthy"}