# Pointer V — Gesture Audit
**Version 2.0.4 · Audited 2026-11-14 · VERIFIED BY READING source files**

---

## 1. Gesture Thresholds, Cooldowns, Hold Times, Hysteresis

### 1.1 Air Single Tap (`gestures.py` lines 221–258)

| Parameter | Value | Source |
|-----------|-------|--------|
| Flexion angle window | last 300 ms of `index_angle_history` (maxlen 15) | `gestures.py:234` |
| Min angle for genuine flexion | `< 130°` (adjustable via `pointing_sensitivity`) | `gestures.py:245–246` |
| Required angle delta (swing) | `≥ 22°` at sens=1.0 | `gestures.py:246` |
| Rebound required | `current_angle > min + 14°` AND `> 140°` | `gestures.py:251` |
| **Tap cooldown** | `max(0.12, tap_cooldown_ms/1000)` → **220 ms** (default) | `gestures.py:253`, `settings.py:59` |
| `last_tap_time` updated | On every detected tap (both tap 1 and tap 2 of a double) | `gestures.py:255` |
| Minimum history frames needed | 5 entries recorded, 4 within window | `gestures.py:231,235` |
| Angle source | `hand.angle_deg(5, 6, 8)` — 2D joint angle, MCP–PIP–TIP | `gestures.py:337` |

### 1.2 Air Double Tap (`gestures.py` lines 584–645)

| Parameter | Value | Source |
|-----------|-------|--------|
| Double-tap window | `double_tap_window_ms` → **320 ms** (default) | `settings.py:57` |
| Window measured from | `tap_start_time` = timestamp of **tap 1 detection** | `gestures.py:644` |
| Second tap acceptance check | `now - tap_start_time <= double_tap_window_s` | `gestures.py:636` |
| Cursor frozen during window? | Yes — position from `history_buffer.get_position_at_lookback(150ms)` | `gestures.py:631,593–595` |
| Single click delay | Delayed until `double_tap_window_ms` expires (pending tap) | `gestures.py:597–606` |

### 1.3 Finger Taps (`finger_taps.py` lines 86–192)

| Parameter | Value | Source |
|-----------|-------|--------|
| Curl measurement | `hand.angle_deg(mcp, pip, tip)` → **2D joint angle** | `finger_taps.py:94` |
| Trajectory window | last **250 ms** | `finger_taps.py:115` |
| Required angle delta | `20° / sens_factor` (index=20°, ring≈16°, pinky≈14.8°) | `finger_taps.py:112` |
| Rebound required | `curr_ang > min + 14°` AND `curr_ang > 130°` | `finger_taps.py:125` |
| Per-finger cooldown | `keyboard.tap_cooldown_ms` → **200 ms** | `finger_taps.py:128`, `settings.py:125` |
| Global neighbor lockout | `keyboard.neighbor_lockout_ms` → **160 ms** | `finger_taps.py:90`, `settings.py:126` |
| Neighbor lockout scope | ALL fingers blocked for 160 ms after ANY finger taps | `finger_taps.py:135,139` |
| Thumb space threshold | angle delta `≥ 18°`, rebound `> 125°`, cooldown 200 ms | `finger_taps.py:182–186` |
| Distance normalization | `hand.distance_3d(0, tip) / hand_scale` (hand_scale = wrist–MCP9) | `finger_taps.py:84,97` |
| Hold-to-repeat delay | `keyboard.key_repeat_delay_s` → **500 ms** | `settings.py:132` |
| Hold-to-repeat rate | `keyboard.key_repeat_rate_cps` → **15 cps** (66.7 ms interval) | `settings.py:133` |

### 1.4 Row Swipe / Window Hop (`mode_manager.py` lines 183–297)

| Parameter | Value | Source |
|-----------|-------|--------|
| Base point | Average of wrist (lm 0) and MCP9 (lm 9) | `mode_manager.py:200–203` |
| Hand size normalization | `distance_3d(0, 9)` — wrist to middle MCP | `mode_manager.py:205` |
| Swipe threshold | **0.32 × hand_size** | `settings.py:123` |
| Swipe cooldown | **300 ms** | `settings.py:124` |
| Neutral-return zone | `dist < 0.22 × hand_size` → resets neutral anchor | `mode_manager.py:217–221` |
| Drift recovery | After 850 ms since last swipe without returning | `mode_manager.py:222–227` |
| Swipe guard: tap in progress | `tap_in_progress` arg blocks swipe evaluation | `mode_manager.py:193` |
| Direction | `|dy| > |dx| AND |dy| >= threshold` → UP/DOWN; `|dx| > |dy| AND |dx| >= threshold` → LEFT/RIGHT | `mode_manager.py:235,249` |

### 1.5 Zone Crossing (`mode_manager.py` lines 258–286)

| Parameter | Value | Source |
|-----------|-------|--------|
| Cross RIGHT (MAIN→SYMBOLS) | Only when at last window of MAIN row; swipe right beyond max | `mode_manager.py:258–264` |
| Cross LEFT (SYMBOLS→MAIN) | Only when at window 0 of SYMBOLS; swipe left | `mode_manager.py:276–282` |
| Memory per zone/row | `zone_window_memory[zone][row]` restored on zone switch | `mode_manager.py:93–102` |

### 1.6 Open Palm → Keyboard Entry (`gestures.py:462–481`, `mode_manager.py:134–151`)

| Parameter | Value | Source |
|-----------|-------|--------|
| Hold time | `keyboard.open_palm_hold_s` → **0.80 s** | `settings.py:120` |
| Hysteresis | 120 ms grace window on UNKNOWN pose (brief flicker allowed) | `gestures.py:482` |
| Suppress after entry | `suppress_keyboard_trigger` flag set externally | `gestures.py:443` |

### 1.7 Fist Hold (POINTER mode pause) (`gestures.py:403–429`)

| Parameter | Value | Source |
|-----------|-------|--------|
| Hold time | `gestures.fist_pause_hold_s` → **1.50 s** | `settings.py:70` |
| Hysteresis | 120 ms grace on UNKNOWN pose | `gestures.py:430` |

### 1.8 Fist Hold (KEYBOARD mode exit) (`mode_manager.py:161–179`)

| Parameter | Value | Source |
|-----------|-------|--------|
| Hold time | `keyboard.fist_close_hold_s` → **0.50 s** | `settings.py:122` |
| Instant exit on POINTING | POINTING pose exits immediately, no hold | `gestures.py:347`, `mode_manager.py:157–159` |

### 1.9 Two-Finger Right Click (`gestures.py:526–578`)

| Parameter | Value | Source |
|-----------|-------|--------|
| Hold time | `gestures.right_click_hold_s` → **0.45 s** | `settings.py:65` |
| Cooldown after right click | 1.5 s | `gestures.py:564` |
| Scroll trigger | `|delta_y| > 0.012` per frame | `gestures.py:549` |

### 1.10 Pinch Brush Lock (`gestures.py:494–514`)

| Parameter | Value | Source |
|-----------|-------|--------|
| Pinch threshold | `gestures.pinch_threshold` → **0.045** (normalized 3D distance) | `settings.py:64` |
| Cooldown | **0.4 s** between toggles | `gestures.py:498` |
| Scope | PAINT mode only | `gestures.py:496` |

### 1.11 Dwell Brush Lock (`gestures.py:187–219`)

| Parameter | Value | Source |
|-----------|-------|--------|
| Hold time | `gestures.dwell_lock_time_s` → **0.60 s** | `settings.py:62` |
| Allowed drift | **0.02** normalized units | `gestures.py:201` |
| Scope | PAINT mode only | `gestures.py:611–621` |

### 1.12 Auto-Pause Watchdog (`gestures.py:319–323`)

| Parameter | Value | Source |
|-----------|-------|--------|
| Timeout | `gestures.auto_pause_timeout_s` → **10 s** | `settings.py:71` |

---

## 2. Settings That Can Block or Delay a Tap

### 2.1 `click_mode` (`settings.py:73`, checked at `gestures.py:523,527,588,599,627`)

| Value | Effect |
|-------|--------|
| `"off"` | All air taps suppressed; pending tap cancelled if mode changes to off mid-flight |
| `"left_only"` | Single and double air taps allowed; RIGHT click (two-finger) suppressed |
| `"all"` | All gestures including right click allowed |

**Default: `"left_only"`** — right clicks disabled out of the box.

### 2.2 Circuit Breaker (`mouse.py:301–324`, enabled by `settings.py:77`)

| Limit | Effect |
|-------|--------|
| > 4 clicks within 2.0 s | `emergency_release()` → all clicks suppressed |
| > 2 right clicks within 5.0 s at same position (< 15 px) | `emergency_release()` |

**A double click counts as 2 events in `click_history`** — if you do 2 double-clicks in 2 seconds, that is 4 events, right at the breaker limit. A third double click would trip it.

### 2.3 Touchpad Yielding (`mouse.py:257–275`)

| Parameter | Effect |
|-----------|--------|
| `yield_distance_px` → **6 px** | If physical pointer moved > 6 px from last Pointer V position, yield for `yield_duration_s` |
| `yield_duration_s` → **1.5 s** | All `move_to()`, `click()`, `double_click()` blocked while yielding |

A tap that arrives during the 1.5 s yield window is **silently dropped** because `click()` returns early if `self.is_yielding`.

### 2.4 `single_click_enabled` (`settings.py:61`, `gestures.py:599`)

Must be `True` (default) for single taps to generate `SINGLE_CLICK` actions after the double-tap window expires.

### 2.5 Confidence Gate (`gestures.py:522,588,627`)

`hand.confidence < 0.50` suppresses all air tap actions and cancels a pending single tap.

### 2.6 Active Region Gate (`gestures.py:518,588,627`)

Hand must be within `active_region` bounds (default 15%–85% of frame). Outside the region, `can_tap = False` and pending tap is cancelled.

---

## 3. Defect Inspection

### (a) Cooldown after tap 1 blocking tap 2 of a double tap — **CONFIRMED**

**Root cause:** `detect_air_tap()` at `gestures.py:253–255` sets `self.last_tap_time = now` on EVERY detected tap, including tap 1 of a double tap. The cooldown check on the next call is:

```python
# gestures.py:254
if flexion_occurred and rebounded and (now - self.last_tap_time > cooldown_s):
    self.last_tap_time = now   # ← updated on tap 1
    return True
```

`cooldown_s = max(0.12, 220/1000) = 0.220 s`.

A natural double tap has its second tap **200–350 ms** after the first. If the inter-tap gap is **< 220 ms**, the second tap is **silently rejected** by the cooldown. Gaps of 200–220 ms (the most natural range) are always dropped.

**Planned fix:** Remove the cooldown between tap 1 and tap 2 when `pending_single_tap == True`. Apply the 220 ms cooldown only after a completed single or double action.

---

### (b) Double-tap window measured from wrong event — **NOT FOUND**

The window IS measured from `tap_start_time`, which is set on tap 1 detection time (`gestures.py:644`). The check at line 636 is `now - tap_start_time <= double_tap_window_s`. This is correct (start-to-start, timestamp-based). However, tap 2 itself is blocked by the cooldown in (a) before it can even reach this check.

---

### (c) Single click fires immediately, double click is a separate later event — **CONFIRMED (by design)**

The code delays the single click until the double-tap window expires (`gestures.py:597–606`). This is the **correct** architecture for avoiding spurious single clicks on double taps. However, the user may notice a **320 ms delay** before every single click, which can feel unresponsive. The "send first click immediately, upgrade to double click on tap 2" pattern is not implemented.

---

### (d) Cursor moves between two taps — **PARTIALLY MITIGATED, still a risk**

The cursor IS frozen at `tap_frozen_pos` during the double-tap window (`gestures.py:593–595`). However, the freeze position is set at **tap 1 detection time** (line 645), not 150 ms before tap 1. During the curl-and-rebound gesture of tap 1, the index finger tip moves, so the cursor position when tap 1 is detected may differ from the resting position before the tap began. The lookback at line 631 (`get_position_at_lookback(150ms)`) correctly gets the pre-tap position, but it only applies to the cursor reported by the DOUBLE_CLICK action itself, not to the freeze that happens on MOVE frames during the pending window.

**Risk:** If `tap_frozen_pos` captures a mid-tap cursor position rather than the pre-tap rest position, the two clicks may not be at the same pixel.

---

### (e) Two clicks sent too close together or too far apart — **CONFIRMED (double_click method)**

`mouse.py:360–368` implements `double_click()` as:
```python
def double_click(self, x=None, y=None):
    if self.is_yielding: return
    if x is not None: self.move_to(x, y)
    self.click()          # DOWN, 15ms sleep, UP
    time.sleep(0.045)     # ← 45 ms inter-click gap
    self.click()          # DOWN, 15ms sleep, UP
```

The inter-click gap of 45 ms is **within** Windows default `GetDoubleClickTime()` (500 ms) and should work. However, `double_click()` is called from the main thread via a Qt signal — if any queued events delay the signal delivery by > ~400 ms, the second click arrives after the system double-click timeout.

Also: the two clicks are sent at the **same position** because `move_to` is called only once before both clicks, which is correct. But `double_click()` calls `self.click()` for both — the first `click()` calls `move_to` again internally. Since `move_to` has a 2 px dead zone, this is safe.

---

### (f) Circuit breaker or click mode dropping second click — **CONFIRMED (double click = 2 events)**

`mouse.py:313`: `if len(clicks_2s) > 4: emergency_release(); return True`

A double click calls `click()` twice, each of which calls `record_click_and_check_breaker`. So a double click **counts as 2 events**. If the user does 2 double-clicks in 2 s (= 4 events), one more single click trips the breaker. The breaker limit should be raised or double-clicks should count as 1 action.

---

### (g) Frame-count vs. timestamp-based timing — **NOT FOUND**

All timing in `gestures.py`, `finger_taps.py`, and `mode_manager.py` uses `time.perf_counter()`. History windows are filtered by `(now - entry[0]) <= 0.25` (seconds). No frame-count arithmetic found.

**Caveat:** The `index_angle_history` deque has `maxlen=15`. At 15 FPS, 15 frames = 1 s, so the `len < 5` guard at `gestures.py:231` could prevent tap detection if FPS drops below ~15. At 30 FPS, all 15 slots fill in 500 ms (well covered). At 60 FPS, 15 frames = 250 ms. The 300 ms window at line 234 may then only contain ~12 of the 15 entries, still sufficient. NOT a frame-count defect, but FPS does affect deque saturation latency at startup.

---

### (h) Left/right mirror — handedness / finger-to-key order — **NOT CONFIRMED, needs recording**

`keyboard_ui.py` has a `finger_mapping` setting (`settings.py:134`, default `"visual"`). The `_paint_zone` and `update_state` methods in `keyboard_ui.py` draw the 4-key window left-to-right as rendered on screen.

**Risk:** MediaPipe reports landmarks in camera-image space. If the camera is **not mirrored** (some front-facing cameras send mirrored, some don't), finger 1 (index) in image space may map to the user's right hand pinky. The code passes `hand.handedness` through (`mode_manager.py:104–111`), but `FingerTapDetector` does not adjust key-to-finger mapping based on handedness — it always maps `("index", "middle", "ring", "pinky")` as the same 4 fingers from landmark indices 8, 12, 16, 20. Whether index → leftmost key or rightmost key is controlled by `finger_mapping` but the mapping itself is not automatically flipped based on the detected handedness label vs. camera mirror state.

**NOT CONFIRMED** as an active defect without a recording. Mark for Phase B verification.

---

### (i) HUD glowing keys vs. logic keys — state desync — **NOT CONFIRMED**

`keyboard_ui.update_state(zone, row_idx, window_idx, ...)` at line 330 is called from the main processing loop with the same `zone`, `row_idx`, `window_idx` values that `mode_manager` holds. The HUD re-fetches the window via `self.layout_manager.get_window(zone, row_idx, window_idx)` using the same `KeyboardLayoutManager` instance. This is a single source of truth — no desync path found.

**Risk:** If the signal/slot queue is backed up, the HUD could display stale state for one frame. This is cosmetic only and would self-correct on the next frame.

---

### (j) Swipes from landmark jitter / palm tilt, threshold not normalized — **NOT CONFIRMED**

The swipe base point (`(wrist.x + mcp9.x)/2`, `(wrist.y + mcp9.y)/2`) is correctly normalized by `hand_size = distance_3d(0, 9)`. The threshold `0.32 × hand_size` is thus scale-invariant.

**Risk:** A wrist-MCP9 midpoint CAN drift if the palm **tilts** (the wrist and MCP9 move relative to each other with rotation, as they are on the same rigid structure). However, since the midpoint moves together with the whole hand, translation-only swipes are detected correctly. Tilt-only without translation would not cross the 0.32 threshold unless the hand is severely angled. NOT CONFIRMED as a defect.

**Risk (jitter):** No velocity requirement exists — a single-frame displacement above 0.32 × hand_size would fire a swipe. With a smooth hand motion, a large jump is unlikely per-frame at 30 FPS, but landmark jitter could contribute. NOT CONFIRMED without a recording.

---

### (k) Swipes firing during taps, taps during swipes — **PARTIALLY MITIGATED**

`mode_manager.evaluate_swipes(hand, tap_in_progress=True)` is blocked by the `tap_in_progress` flag. The caller in `main.py` must pass `tap_in_progress=True` when a finger tap is in progress. NOT TESTED whether `main.py` passes this correctly.

Air-tap detection in KEYBOARD mode: `gestures.py:340–371` returns early with `GestureAction.PAUSE` or `EXIT_KEYBOARD` in KEYBOARD mode — the air-tap code at lines 626–653 is **not reached** in KEYBOARD mode. So air taps cannot fire swipes in keyboard mode and vice versa. Finger taps are handled separately by `FingerTapDetector` in `main.py`.

---

### (l) Per-finger curl from 2D positions — **CONFIRMED**

`finger_taps.py:62`: `pip_angle = hand.angle_deg(mcp_idx, pip_idx, tip_idx)`

`hand.angle_deg()` is computed from `hand.get(idx).x`, `hand.get(idx).y` — **2D coordinates** from the MediaPipe normalized image landmarks. 3D world landmarks are not used.

**Impact:** 2D angles change with:
- Hand rotation (tilting the wrist changes all 2D angles without actual flexion)
- Camera distance changes (perspective distortion)
- Hand pronation/supination

Similarly, `gestures.py:337` uses `hand.angle_deg(5, 6, 8)` for air-tap detection (also 2D).

**Planned fix for Phase C/D:** Use `hand.distance_3d()` (which uses 3D world landmark coordinates, `hand.get(idx).z` as returned by MediaPipe) normalized by `hand_scale`, or switch angle computation to use all 3 coordinates.

---

### (m) Fixed absolute threshold, no per-finger baseline — **CONFIRMED**

`finger_taps.py:112`: `base_threshold = 20.0 / max(0.4, sens_factor)`

This is a **fixed absolute angle swing** (20°) with only a static per-finger sensitivity factor. There is no adaptive baseline computed from recent non-tapping frames. If a user has naturally curled ring or pinky fingers at rest, the resting angle is higher, making the detected delta smaller than the threshold, suppressing taps.

**Planned fix:** Compute a rolling baseline angle (mean over last ~0.5 s of non-tapping frames) per finger; trigger on `angle - baseline > threshold_fraction * calibrated_range`.

---

### (n) Neighbor lockout — **PARTIALLY CONFIRMED**

The global `last_any_tap_time` lockout (160 ms) prevents ALL other fingers from tapping for 160 ms after any finger taps. This is correct for preventing cross-fire but means:
- Rapid consecutive taps on different fingers (e.g., alternating index and middle) are impossible faster than 160 ms apart (~6.25 taps/s max with alternating fingers)
- Thumb space tap: blocked by neighbor lockout 160 ms after any typing finger fires (line 185)

**Thumb/space conflict:** If a typing finger accidentally fires when the user tries to do a thumb tap, the thumb tap is blocked for 160 ms. For fast typing, this is usually fine. For the thumb-space gesture, the user typically uses a different motion, so co-firing is unlikely. NOT CONFIRMED as a practical problem without recording.

---

### (o) Exception swallowing — **NOT CONFIRMED**

No bare `except: pass` patterns found in the gesture path. `mouse.py` and `keyboard_out.py` do have `except Exception: pass` around Win32 calls, but these log nothing and return safely. The processing loop in `main.py` (from previous audit) has an outer exception handler that emits a signal — gesture exceptions would propagate up and be reported. NOT CONFIRMED as silent drops.

---

## 4. Confirmed Defects and Planned Fixes

| ID | Defect | Severity | Planned Fix |
|----|--------|----------|-------------|
| **a** | 220 ms tap cooldown blocks tap 2 of natural double tap (200–220 ms gap) | **CRITICAL** | Skip cooldown check when `pending_single_tap == True`; apply cooldown only after a completed action |
| **c** | 320 ms delay before every single click (by design, but feels sluggish) | **HIGH** | Add "immediate first click" option: send click 1 immediately, cancel with double if tap 2 arrives |
| **d** | Freeze position is set at tap-1 detection time (mid-motion), not 150 ms pre-tap | **HIGH** | Use `history_buffer.get_position_at_lookback(150ms)` for `tap_frozen_pos` on tap 1 |
| **e** | `double_click()` via queued Qt signal may arrive late; both clicks use same 45 ms gap | **MEDIUM** | Measure actual delivery latency; adjust inter-click gap; consider `GetDoubleClickTime()` |
| **f** | Circuit breaker counts double click as 2 events, trips at 2 double-clicks + 1 click/2s | **MEDIUM** | Count a logical double-click dispatch as 1 action in `click_history` |
| **l** | 2D landmark angles for curl detection (angle changes with hand tilt/rotation) | **HIGH** | Use `hand.distance_3d(0, tip) / hand_scale` as primary curl signal, or 3D joint vectors |
| **m** | Fixed absolute tap threshold, no per-finger adaptive baseline | **HIGH** | Rolling per-finger baseline over last 500 ms of idle frames; trigger on delta from baseline |

---

## 5. Additional Observations (Not Defects, But Risks)

- **Camera resolution:** Default `camera_width=1280, camera_height=720`. MediaPipe landmark jitter is proportional to resolution; higher resolution = more stable landmarks = better curl accuracy.
- **FPS during keyboard mode:** `target_fps=60` default. If actual FPS < 25, the 250 ms trajectory window may contain only 6 frames, reducing detection reliability. Phase B should measure actual FPS.
- **Swipe no velocity requirement:** A single frame above threshold fires. Consider requiring sustained displacement over ≥ 2 consecutive frames.
- **`double_click()` calls `move_to()` only once** (before both clicks). This is correct. But the second `self.click()` internally does not move — good.
- **`keyboard_ui` `active_zone` / `current_row` / `current_window_idx`** are set exactly from the values `mode_manager` holds, via `update_state()`. No desync path was found — defect (i) is NOT CONFIRMED.
- **`key_repeat_interval_s` property** correctly computes from `key_repeat_rate_cps` (15 cps → 66.7 ms). No frame-count issues.
- **Swipe resets `hand_returned_to_neutral = False`** on every swipe. The hand must return to within 0.22 × hand_size of the neutral anchor before the next swipe can fire. This correctly prevents double-jumps, but if the user moves their hand to a new resting position and holds it, the 850 ms drift recovery (`mode_manager.py:222`) resets the neutral anchor there. This means a slow sustained motion could fire 1 swipe then wait 850 ms and fire another — a "slow double-jump." NOT CONFIRMED as a practical problem.

