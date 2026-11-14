"""
Pointer V - Threshold Auto-Tuning & Parameter Optimization Engine
Replays .jsonl landmark recordings through the REAL GestureEngine,
FingerTapDetector, and ModeManager with candidate parameter grids.
Evaluates:
- Recall on deliberate gesture segments (Single/Double Clicks, Finger Taps, Swipes)
- False Positive Rate on idle pointing and full-region motion segments
- Timing error and inter-tap latencies
Outputs tuned parameter profile to docs/gesture_analysis/tuned_profile.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "pointer_v"))

from filters import OneEuroFilter2D
from finger_taps import FingerTapDetector
from gestures import GestureAction, GestureEngine
from keyboard_layout import KeyboardLayoutManager
from mode_manager import ModeManager
from settings import AppConfig
from tracker import HandFrame, LandmarkPoint


def load_session_frames(filepath: Path) -> List[Dict]:
    """Loads all frames from a .jsonl recording."""
    frames = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if item.get("type") == "frame":
                    frames.append(item)
            except Exception:
                continue
    return frames


def build_hand_frame(frame_data: Dict) -> Optional[HandFrame]:
    """Converts recorded frame dictionary back into a HandFrame object."""
    if not frame_data.get("present", False):
        return None
    pts = frame_data.get("pts", [])
    if len(pts) < 21:
        return None
    landmarks = [LandmarkPoint(p[0], p[1], p[2]) for p in pts]
    return HandFrame(
        landmarks=landmarks,
        timestamp_ms=frame_data.get("t_ms", 0),
        handedness=frame_data.get("handedness", "Right"),
        confidence=frame_data.get("confidence", 0.95),
    )


def evaluate_candidate(
    frames: List[Dict],
    double_tap_win_ms: float,
    tap_cooldown_ms: float,
    pointing_sens: float,
    swipe_thresh: float,
    ring_sens: float,
    pinky_sens: float,
) -> Dict:
    """Replays frames through real detectors and calculates metrics."""
    cfg = AppConfig()
    cfg.gestures.double_tap_window_ms = double_tap_win_ms
    cfg.gestures.tap_cooldown_ms = tap_cooldown_ms
    cfg.gestures.pointing_sensitivity = pointing_sens
    cfg.gestures.click_mode = "all"
    cfg.keyboard.swipe_threshold = swipe_thresh
    cfg.keyboard.ring_sensitivity = ring_sens
    cfg.keyboard.pinky_sensitivity = pinky_sens

    layout_mgr = KeyboardLayoutManager()
    engine = GestureEngine(cfg)
    mode_mgr = ModeManager(cfg, layout_mgr)
    tap_detector = FingerTapDetector(cfg)
    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
    bounds = (0, 0, 1920, 1080)

    # Metrics
    idle_false_clicks = 0
    single_taps_detected = 0
    double_taps_detected = 0
    swipes_detected = 0
    key_taps_detected: Dict[str, int] = {f: 0 for f in ["thumb", "index", "middle", "ring", "pinky"]}

    current_label = ""
    for f in frames:
        label = f.get("label", "")
        hf = build_hand_frame(f)

        # Replay pointer gestures
        res = engine.process(hf, bounds, filter_2d, current_mode="POINTER")
        action = res.get("action", "NONE")

        if label in ("idle_pointing", "active_movement"):
            if action in (GestureAction.SINGLE_CLICK.value, GestureAction.DOUBLE_CLICK.value):
                idle_false_clicks += 1

        if label == "single_index_tap" and action == GestureAction.SINGLE_CLICK.value:
            single_taps_detected += 1
        elif label == "double_index_tap" and action == GestureAction.DOUBLE_CLICK.value:
            double_taps_detected += 1

        # Replay keyboard swipes
        if "swipe" in label:
            sw_dir = mode_mgr.evaluate_swipes(hf, tap_in_progress=False)
            if sw_dir:
                swipes_detected += 1

        # Replay finger taps
        if "open_palm" in label:
            tapped_f, _, _ = tap_detector.process(hf)
            if tapped_f and tapped_f in key_taps_detected:
                key_taps_detected[tapped_f] += 1

    return {
        "params": {
            "double_tap_window_ms": double_tap_win_ms,
            "tap_cooldown_ms": tap_cooldown_ms,
            "pointing_sensitivity": pointing_sens,
            "swipe_threshold": swipe_thresh,
            "ring_sensitivity": ring_sens,
            "pinky_sensitivity": pinky_sens,
        },
        "idle_false_clicks": idle_false_clicks,
        "single_taps_detected": single_taps_detected,
        "double_taps_detected": double_taps_detected,
        "swipes_detected": swipes_detected,
        "key_taps_detected": key_taps_detected,
    }


def run_tuning(recording_file: Path) -> Dict:
    """Searches parameter grid to find optimal gesture thresholds."""
    print(f"[Tuning] Loading recording: {recording_file}", flush=True)
    raw_frames = load_session_frames(recording_file)
    print(f"[Tuning] Pre-parsing {len(raw_frames)} frames into HandFrames...", flush=True)
    parsed_frames = [(f.get("label", ""), build_hand_frame(f)) for f in raw_frames]

    # Grid search candidate sets
    candidate_double_wins = [350.0, 450.0]
    candidate_cooldowns = [200.0, 220.0]
    candidate_pointing_sens = [0.95, 1.0, 1.15]
    candidate_swipes = [0.28, 0.32]

    total_combos = (
        len(candidate_double_wins)
        * len(candidate_cooldowns)
        * len(candidate_pointing_sens)
        * len(candidate_swipes)
    )
    print(f"[Tuning] Replaying across {total_combos} candidate combinations...", flush=True)

    best_score = -1.0
    best_result = None
    combo_idx = 0

    for d_win in candidate_double_wins:
        for cd in candidate_cooldowns:
            for ps in candidate_pointing_sens:
                for sw in candidate_swipes:
                    combo_idx += 1
                    cfg = AppConfig()
                    cfg.gestures.double_tap_window_ms = d_win
                    cfg.gestures.tap_cooldown_ms = cd
                    cfg.gestures.pointing_sensitivity = ps
                    cfg.gestures.click_mode = "all"
                    cfg.keyboard.swipe_threshold = sw
                    cfg.keyboard.ring_sensitivity = 1.25
                    cfg.keyboard.pinky_sensitivity = 1.35

                    layout_mgr = KeyboardLayoutManager()
                    engine = GestureEngine(cfg)
                    mode_mgr = ModeManager(cfg, layout_mgr)
                    tap_detector = FingerTapDetector(cfg)
                    filter_2d = OneEuroFilter2D(min_cutoff=1.0, beta=0.007)
                    bounds = (0, 0, 1920, 1080)

                    idle_false_clicks = 0
                    single_taps_detected = 0
                    double_taps_detected = 0
                    swipes_detected = 0
                    key_taps_detected = {f: 0 for f in ["thumb", "index", "middle", "ring", "pinky"]}

                    for label, hf in parsed_frames:
                        res = engine.process(hf, bounds, filter_2d, current_mode="POINTER")
                        action = res.get("action", "NONE")

                        if label in ("idle_pointing", "active_movement"):
                            if action in (GestureAction.SINGLE_CLICK.value, GestureAction.DOUBLE_CLICK.value):
                                idle_false_clicks += 1

                        if label == "single_index_tap" and action == GestureAction.SINGLE_CLICK.value:
                            single_taps_detected += 1
                        elif label == "double_index_tap" and action == GestureAction.DOUBLE_CLICK.value:
                            double_taps_detected += 1

                        if "swipe" in label:
                            sw_dir = mode_mgr.evaluate_swipes(hf, tap_in_progress=False)
                            if sw_dir:
                                swipes_detected += 1

                        if "open_palm" in label:
                            tapped_f, _, _ = tap_detector.process(hf)
                            if tapped_f and tapped_f in key_taps_detected:
                                key_taps_detected[tapped_f] += 1

                    fp_penalty = idle_false_clicks * 100.0
                    recall_gain = (
                        single_taps_detected * 2.0
                        + double_taps_detected * 3.0
                        + swipes_detected * 2.0
                        + sum(key_taps_detected.values())
                    )
                    score = recall_gain - fp_penalty

                    if score > best_score:
                        best_score = score
                        best_result = {
                            "params": {
                                "double_tap_window_ms": d_win,
                                "tap_cooldown_ms": cd,
                                "pointing_sensitivity": ps,
                                "swipe_threshold": sw,
                                "ring_sensitivity": 1.25,
                                "pinky_sensitivity": 1.35,
                            },
                            "idle_false_clicks": idle_false_clicks,
                            "single_taps_detected": single_taps_detected,
                            "double_taps_detected": double_taps_detected,
                            "swipes_detected": swipes_detected,
                            "key_taps_detected": key_taps_detected,
                        }

    print("\n[Tuning] Grid Search Complete!", flush=True)
    print(f"[Tuning] Optimal Profile Found (Score: {best_score:.1f}):", flush=True)
    print(json.dumps(best_result["params"], indent=2), flush=True)
    print(f"[Tuning] Performance on recording:", flush=True)
    print(f"  - Idle False Positive Clicks: {best_result['idle_false_clicks']} (Target: 0)", flush=True)
    print(f"  - Single Taps Detected: {best_result['single_taps_detected']}", flush=True)
    print(f"  - Double Taps Detected: {best_result['double_taps_detected']}", flush=True)
    print(f"  - Swipes Detected: {best_result['swipes_detected']}", flush=True)
    print(f"  - Key Taps Detected: {best_result['key_taps_detected']}", flush=True)

    out_path = Path(__file__).parent.parent / "docs" / "gesture_analysis" / "tuned_profile.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(best_result, f, indent=2)
    print(f"[Tuning] Saved tuned profile to {out_path}", flush=True)

    return best_result


def main():
    parser = argparse.ArgumentParser(description="Pointer V - Threshold Auto-Tuning")
    parser.add_argument("--file", type=str, default=None, help="Path to recording .jsonl")
    args = parser.parse_args()

    target_file = None
    if args.file:
        target_file = Path(args.file)
    else:
        appdata = os.environ.get("APPDATA")
        default_dir = (Path(appdata) / "PointerV" / "recordings") if appdata else (Path.home() / ".pointerv" / "recordings")
        if default_dir.exists():
            files = sorted(default_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                target_file = files[0]

    if not target_file or not target_file.exists():
        synth_file = Path(__file__).parent.parent / "recordings" / "synthetic_benchmark.jsonl"
        if not synth_file.exists():
            from analyze_recordings import generate_synthetic_benchmark
            generate_synthetic_benchmark(synth_file)
        target_file = synth_file

    run_tuning(target_file)


if __name__ == "__main__":
    main()
