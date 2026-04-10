"""
Difficulty Adapter — K-Means Clustering
=========================================
Clusters historical pose scores into STRONG / MODERATE / WEAK
performance bands. Returns:
  - weak_zones   : poses the user consistently struggles with
  - strong_poses : poses the user has mastered
  - next_session : recommended pose sequence (targets weak areas first,
                   bookended by strong poses for confidence)

Falls back gracefully when there's not enough data yet
(< MIN_SAMPLES pose logs).
"""

import json
from collections import defaultdict
from typing import Optional

# Require at least this many logged attempts before clustering
MIN_SAMPLES = 10

# K-Means cluster count
N_CLUSTERS = 3   # weak / moderate / strong

# Similarity score thresholds for the cluster labels
# (used to label clusters after fitting, not for assignment)
WEAK_CEIL     = 0.60
MODERATE_CEIL = 0.80
# > 0.80 → strong

# All supported poses (must match pose_checkers keys in main.py)
ALL_POSES = [
    "Triangle", "Tree", "T", "Crescent_lunge", "Warrior", "Mountain",
    "Bridge", "Cat-Cow", "Cobra", "Seated", "Standing",
    "Downward Dog", "Lotus", "Pigeon", "Legs-Up-The-Wall",
]


# ── Pure-Python K-Means (no sklearn dependency) ────────────────────────────────

def _kmeans_1d(values: list[float], k: int = 3, iterations: int = 100):
    """
    Minimal 1-D K-Means. Returns (labels, centroids).
    labels[i] ∈ {0,1,...,k-1}
    """
    import random
    if len(values) < k:
        return list(range(len(values))), sorted(values)

    centroids = sorted(random.sample(values, k))

    for _ in range(iterations):
        # Assignment
        labels = [
            min(range(k), key=lambda j: abs(v - centroids[j]))
            for v in values
        ]
        # Update
        new_centroids = []
        for j in range(k):
            cluster = [values[i] for i, l in enumerate(labels) if l == j]
            new_centroids.append(sum(cluster) / len(cluster) if cluster else centroids[j])

        if new_centroids == centroids:
            break
        centroids = new_centroids

    return labels, centroids


def _label_cluster(centroid: float) -> str:
    if centroid < WEAK_CEIL:
        return "weak"
    elif centroid < MODERATE_CEIL:
        return "moderate"
    return "strong"


# ── Main adapter ───────────────────────────────────────────────────────────────

def analyze(pose_logs: list[dict]) -> dict:
    """
    pose_logs: list of dicts from session_store.get_all_pose_logs()
    Each dict: {pose_name, avg_similarity, peak_similarity, reps, hold_sec}

    Returns:
    {
        "status": "ok" | "insufficient_data",
        "pose_stats": {pose: {avg, peak, attempts}},
        "clusters":   {pose: "weak"|"moderate"|"strong"},
        "weak_zones": [pose, ...],
        "strong_poses": [pose, ...],
        "next_session": [pose, ...],  # recommended order
        "insight": str,               # human-readable summary
    }
    """

    if len(pose_logs) < MIN_SAMPLES:
        return {
            "status": "insufficient_data",
            "message": f"Need at least {MIN_SAMPLES} pose attempts to adapt. "
                       f"Keep practising — only {len(pose_logs)} logged so far.",
            "weak_zones":   [],
            "strong_poses": [],
            "next_session": ALL_POSES[:5],   # default beginner sequence
        }

    # ── Aggregate per pose ────────────────────────────────────────────────────
    buckets: dict[str, list[float]] = defaultdict(list)
    peaks:   dict[str, list[float]] = defaultdict(list)

    for log in pose_logs:
        name = log["pose_name"]
        buckets[name].append(log["avg_similarity"])
        peaks[name].append(log["peak_similarity"])

    pose_stats = {}
    for name, sims in buckets.items():
        pose_stats[name] = {
            "avg":      round(sum(sims) / len(sims), 4),
            "peak":     round(max(peaks[name]), 4),
            "attempts": len(sims),
        }

    # ── K-Means on average similarities ───────────────────────────────────────
    names  = list(pose_stats.keys())
    avgs   = [pose_stats[n]["avg"] for n in names]

    # Need at least 2 distinct poses to form meaningful clusters
    if len(names) < 2:
        only  = names[0]
        label = _label_cluster(avgs[0])
        return {
            "status":       "ok",
            "pose_stats":   pose_stats,
            "clusters":     {only: label},
            "weak_zones":   [only] if label == "weak" else [],
            "strong_poses": [only] if label == "strong" else [],
            "next_session": [only],
            "insight":      f"Only {only} practiced so far. Try more poses to unlock full analysis.",
        }

    labels, centroids = _kmeans_1d(avgs, k=min(N_CLUSTERS, len(names)))

    # Sort centroids ascending so label 0 = lowest = weakest
    sorted_centroids = sorted(enumerate(centroids), key=lambda x: x[1])
    rank_map = {orig_idx: rank for rank, (orig_idx, _) in enumerate(sorted_centroids)}

    clusters: dict[str, str] = {}
    for i, name in enumerate(names):
        cluster_rank = rank_map[labels[i]]
        centroid_val = sorted(centroids)[cluster_rank]
        clusters[name] = _label_cluster(centroid_val)

    weak_zones   = [n for n, c in clusters.items() if c == "weak"]
    strong_poses = [n for n, c in clusters.items() if c == "strong"]
    moderate     = [n for n, c in clusters.items() if c == "moderate"]

    # Sort each group by avg score ascending (hardest first within group)
    weak_zones   = sorted(weak_zones,   key=lambda n: pose_stats[n]["avg"])
    strong_poses = sorted(strong_poses, key=lambda n: pose_stats[n]["avg"], reverse=True)

    # ── Build recommended next session ────────────────────────────────────────
    # Pattern: 1 strong (warm-up confidence) → weak poses → moderate → 1 strong (close)
    next_session: list[str] = []
    if strong_poses:
        next_session.append(strong_poses[-1])       # easiest strong as warm-up
    next_session.extend(weak_zones[:3])              # up to 3 weakest first
    next_session.extend(moderate[:2])                # 2 moderate for variety
    if len(strong_poses) > 1:
        next_session.append(strong_poses[0])         # best strong to close

    # Deduplicate while preserving order
    seen: set[str] = set()
    next_session = [p for p in next_session if not (p in seen or seen.add(p))]

    # ── Human-readable insight ────────────────────────────────────────────────
    if weak_zones:
        focus = ", ".join(weak_zones[:2])
        insight = (
            f"Your data shows {len(weak_zones)} pose(s) need attention — "
            f"especially {focus}. Your next session targets these first."
        )
    else:
        insight = "Solid performance across all poses! Keep pushing your hold durations."

    return {
        "status":       "ok",
        "pose_stats":   pose_stats,
        "clusters":     clusters,
        "weak_zones":   weak_zones,
        "strong_poses": strong_poses,
        "next_session": next_session,
        "insight":      insight,
    }


def get_recommendation(pose_logs: list[dict], current_pose: str) -> Optional[str]:
    """
    Quick helper: returns a single recommended NEXT pose to try,
    or None if data is insufficient.
    """
    result = analyze(pose_logs)
    if result["status"] != "ok":
        return None

    seq = result["next_session"]
    try:
        idx = seq.index(current_pose)
        return seq[(idx + 1) % len(seq)]
    except ValueError:
        return seq[0] if seq else None
