"""
Rep Counter — State Machine Approach
=====================================
No training data or LSTM required. Works by tracking the
similarity score over time and detecting "dip → hold → dip"
cycles to count a completed rep.

A rep is counted when:
  1. Score rises above ENTRY_THRESHOLD  (user enters pose)
  2. Score stays above HOLD_THRESHOLD   for at least MIN_HOLD_FRAMES (user holds it)
  3. Score drops below EXIT_THRESHOLD   (user exits pose)

This maps naturally onto yoga reps (flow sequences) and hold-and-release patterns.
"""

from collections import deque
import time


# ── Tunable thresholds ─────────────────────────────────────────────────────────
ENTRY_THRESHOLD = 0.65   # score must cross this to begin a potential hold
HOLD_THRESHOLD  = 0.70   # score must stay above this to count as "held"
EXIT_THRESHOLD  = 0.55   # score must drop below this to close the rep
MIN_HOLD_SEC    = 1.5    # minimum seconds the pose must be held to count as a rep
SMOOTHING_WIN   = 8      # rolling-average window (frames) to reduce jitter
# ───────────────────────────────────────────────────────────────────────────────


class RepCounter:
    """
    Tracks rep count and hold duration for a single pose session.

    Usage (call once per frame inside process_frames):
        counter = RepCounter()
        result  = counter.update(similarity_score)   # float 0-1
        # result keys: reps, hold_sec, state, peak_score
    """

    def __init__(self):
        self._window:      deque[float] = deque(maxlen=SMOOTHING_WIN)
        self.reps:         int   = 0
        self.state:        str   = "idle"   # idle | entering | holding | exiting
        self._hold_start:  float | None = None
        self._peak_score:  float = 0.0
        self._hold_sec:    float = 0.0      # duration of the last completed hold

    # ── public ────────────────────────────────────────────────────────────────

    def update(self, raw_score: float) -> dict:
        """
        Feed the latest similarity score. Returns the current rep state.
        Call once per frame.
        """
        self._window.append(raw_score)
        score = sum(self._window) / len(self._window)   # smoothed

        now = time.time()

        if self.state == "idle":
            if score >= ENTRY_THRESHOLD:
                self.state       = "entering"
                self._hold_start = now
                self._peak_score = score

        elif self.state == "entering":
            self._peak_score = max(self._peak_score, score)
            if score >= HOLD_THRESHOLD:
                self.state = "holding"
            elif score < EXIT_THRESHOLD:
                # never reached hold quality — reset
                self.state       = "idle"
                self._hold_start = None

        elif self.state == "holding":
            self._peak_score = max(self._peak_score, score)
            if score < EXIT_THRESHOLD:
                held = now - (self._hold_start or now)
                if held >= MIN_HOLD_SEC:
                    self.reps      += 1
                    self._hold_sec  = round(held, 1)
                self.state       = "exiting"
                self._hold_start = None

        elif self.state == "exiting":
            # brief cool-down so a shaky exit doesn't re-trigger immediately
            if score < EXIT_THRESHOLD - 0.05:
                self.state = "idle"

        current_hold = 0.0
        if self.state in ("holding", "entering") and self._hold_start:
            current_hold = round(now - self._hold_start, 1)

        return {
            "reps":        self.reps,
            "hold_sec":    current_hold,
            "last_hold":   self._hold_sec,
            "state":       self.state,
            "peak_score":  round(self._peak_score, 3),
            "smoothed":    round(score, 3),
        }

    def reset(self):
        self.__init__()

    def summary(self) -> dict:
        return {
            "total_reps": self.reps,
            "last_hold_sec": self._hold_sec,
        }
