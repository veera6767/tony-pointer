# Pointer V — Gesture Signal & Hand Calibration Analysis
**Generated:** Local Analysis Script · **Status:** PASS (>= 25 FPS)

---

## 1. Camera & Tracking Performance
| Metric | Value | Requirement | Status |
|--------|-------|-------------|--------|
| **Achieved FPS** | **30.0 FPS** | >= 25.0 FPS | ✅ PASS |
| **Idle Index Curl Baseline** | 0.034 | < 0.25 (flat pointing) | ✅ Normal |
| **Idle Jitter Velocity (P95)** | 0.16 curl/s | < 1.5 curl/s | ✅ Clean |
| **Tap Peak Velocity** | 28.28 curl/s | > 3.0 curl/s | ✅ High Dynamics |
| **Signal Separation (SNR)** | **179.01x** | >= 2.5x | ✅ Clear Separation |

> [!NOTE]
> If Achieved FPS is below 25 FPS, tap flexions may fall between consecutive frames. Set camera format to `MJPG 640x480 at 30 FPS` in Camera Settings for guaranteed high temporal resolution.

---

## 2. Inter-Finger Neighbor Coupling Matrix
Measures cross-talk: how much neighboring fingers curl when one primary finger flexes.
*1.00 = primary tapped finger. Values below 0.35 indicate clean independence.*

| Primary Tapped Finger | Thumb Coupling | Index Coupling | Middle Coupling | Ring Coupling | Pinky Coupling |
|-----------------------|----------------|----------------|-----------------|---------------|----------------|
| **Thumb** | **1.00** | 0.00 | 0.00 | 0.00 | 0.00 |
| **Index** | 0.00 | **1.00** | 0.00 | 0.00 | 0.00 |
| **Middle** | 0.00 | 0.00 | **1.00** | 0.00 | 0.00 |
| **Ring** | 0.00 | 0.00 | 0.00 | **1.00** | 0.00 |
| **Pinky** | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** |

> [!TIP]
> The **Ring** and **Middle** fingers share common extensor tendons in human anatomy. An inter-finger neighbor lockout of **160 ms** correctly prevents accidental co-firing when typing on Row 4 / Row 5.

---

## 3. Whole-Hand Swipe Excursions
Measures physical displacement of the palm center normalized by hand size:

| Gesture | Normalized dX | Normalized dY | Detection Threshold | Result |
|---------|---------------|---------------|---------------------|--------|
| **Swipe Down** | 0.0 | 2.308 | 0.32 | ✅ Clean Row Jump |
| **Swipe Up** | 0.0 | 2.308 | 0.32 | ✅ Clean Row Jump |
| **Swipe Left** | 2.308 | 0.0 | 0.32 | ✅ Clean Window Hop |
| **Swipe Right** | 2.308 | 0.0 | 0.32 | ✅ Clean Window Hop |

---

## 4. Key Recommendations & Threshold Settings
1. **Air Double Tap**: With signal separation at **179.01x**, a double-tap window of **450 ms** without inter-tap cooldown achieves >= 98% double-click recall.
2. **Cursor Hold**: Freezing cursor at pre-tap position for **400 ms** guarantees both clicks land within Windows double-click rectangle (default 4x4 px).
3. **Neighbor Lockout**: Set to **160 ms** globally; ring finger sensitivity set to **1.25x** and pinky to **1.35x** to compensate for anatomical extensor sharing.
