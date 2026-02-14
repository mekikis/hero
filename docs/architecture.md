# Hero Architecture

Version: 0.1 (Feb 2026)  
Target platform: Jetson Orin Nano (JetPack 6 / Ubuntu 22.04)  
Backbone: **ROS 2** (recommended: Humble on 22.04)

---

## Goals

- Make Hero scalable: multiple subsystems can evolve independently without breaking each other.
- Make it debuggable: record/replay, metrics, logs, reproducible deployments.
- Make it interactive: buttons/gesture/UI unify into “intents”; uncertain perception triggers questions.
- Make it deployable: container-first, consistent configs, safe hardware access on Jetson.

---

## System map

### Platform
- **Bringup & Orchestration**: launches everything, manages modes, lifecycle, restarts.
- **ROS 2 Interfaces**: message/action/service definitions, versioned and shared across nodes.
- **Config & Secrets**: environment profiles, calibration, device mapping.
- **Telemetry & Health**: metrics, logs, diagnostics, heartbeats.
- **Data Recording & Replay**: rosbag2 profiles for “vision runs”, “full runs”.

### Perception & Inputs
- **Vision Stack**: CSI camera capture → preprocessing → detection/segmentation → tracking → scene semantics.
- **Open-world Recognition & Learning**: “unknown” logic + ask loop + local memory of labeled objects.
- **Inputs Stack**: gesture device + physical buttons → normalized input events.

### Cognition & Control
- **Intent Router**: normalizes UI/gesture/voice into high-level intents.
- **Behavior Engine**: state machine that decides what Hero does next.
- **Navigation/Safety**: later: free-space, obstacle avoidance, planning; safety constraints.
- **Actuation Control**: later: motion/servo control.

### User Interaction
- **UI Dashboard**: live status, buttons, “label this” prompts, logs, recordings controls.
- **Ask the Human**: question generation + presenting crop + capturing label + confirming.

---

## ROS 2 graph and contracts

### Packages
- `hero_interfaces` (messages/actions/services)  
- `hero_bringup` (launch files, param sets, profiles)  
- `hero_vision_capture` (camera node)  
- `hero_vision_perception` (det/seg/tracking)  
- `hero_inputs` (gesture + buttons)  
- `hero_intents` (router)  
- `hero_behavior` (state machine)  
- `hero_ui_bridge` (web UI ↔ ROS 2)  
- `hero_telemetry` (metrics exporter, diagnostics aggregation)

---

## Topics, Services, Actions

### Camera / Vision
**Topics**
- `/camera/frame_meta` (`hero_interfaces/FrameMeta`)
  - `frame_id, stamp, width, height, fps, dropped_frames`
- `/camera/image` (`sensor_msgs/Image`) OR `/camera/image/compressed`
  - Start with standard ROS image; move to compressed if bandwidth needed.
- `/vision/detections` (`hero_interfaces/Detections`)
  - array of `Detection {label, confidence, bbox, side, track_id?}`
- `/vision/scene_summary` (`hero_interfaces/SceneSummary`)
  - lightweight: `left_objects[], right_objects[], center_objects[]` + occupancy estimates
- `/vision/unknown_candidates` (`hero_interfaces/UnknownCandidateArray`)
  - `candidate_id, frame_id, bbox, confidence, crop_ref`
- `/vision/tracks` (`hero_interfaces/Tracks`) (later)

**Services**
- `/vision/set_mode` (`hero_interfaces/SetVisionMode`)
  - enable/disable detection, segmentation, unknown-asking, etc.
- `/vision/capture_snapshot` (`hero_interfaces/CaptureSnapshot`)
  - returns file path / ID

**Actions**
- `/vision/record_clip` (`hero_interfaces/RecordClip.action`)
  - goal: duration, quality, tags → result: file refs, stats

### Inputs and Intents
**Topics**
- `/input/button` (`hero_interfaces/ButtonEvent`)
- `/input/gesture` (`hero_interfaces/GestureEvent`)
- `/hero/intent` (`hero_interfaces/Intent`)
  - unified commands: `record`, `toggle_mode`, `label_unknown`, `follow_target`, etc.

**Services**
- `/hero/set_profile` (`hero_interfaces/SetProfile`)
  - e.g., `home`, `dev`, `quiet`, etc.

### Ask / Learning loop
**Topics**
- `/ask/request` (`hero_interfaces/AskRequest`)
  - `candidate_id, prompt, crop_ref, choices[]?`
- `/ask/response` (`hero_interfaces/AskResponse`)
  - `candidate_id, label, confirmed, notes`

**Services**
- `/learning/add_label` (`hero_interfaces/AddLabel`)
- `/learning/list_known` (`hero_interfaces/ListKnownObjects`)

### Telemetry
**Topics**
- `/system/health` (`hero_interfaces/SystemHealth`)
- `/diagnostics` (`diagnostic_msgs/DiagnosticArray`) (optional)

---

## Data transport strategy for images

Start pragmatic, upgrade later:

### Phase 1 (simple)
- `/camera/image` as ROS Image (BGR8/RGB8) or compressed.
- Use rosbag2 to record and replay.

### Phase 2 (performance)
- Keep `/camera/frame_meta` in ROS.
- Frames in a **shared-memory ring buffer** referenced by `frame_id`.
- Perception reads frames by `frame_id` to avoid copying.

Rule: never stream raw images over a general-purpose broker outside ROS; use ROS image transport or shared memory.

---

## “Unknown → Ask → Learn” policy

### Unknown trigger (recommended initial policy)
Trigger candidate if:
- detection confidence < `CONF_LOW` (e.g., 0.35)
- bbox area ratio > `MIN_AREA` (e.g., 0.02 of frame)
- persists for `N` frames (e.g., 10 frames) with similar location/size
- not recently dismissed (cooldown per region/object)

### Ask behavior
- Save crop artifact: `runs/asks/<candidate_id>.jpg`
- Publish `/ask/request` with:
  - prompt: “What is this object on the left?”
  - crop_ref: file path or id
  - optional choices: top-k labels if open-vocab is enabled later

### Learn v0
- Append label to `runs/labels.csv` and store crop.
- Update a simple memory index (later: embeddings + nearest-neighbor).

---

## Containerization plan on Jetson

### Philosophy
- Keep **camera access stable first**.
- Containerize once you can run reliably on-host.
- Use NVIDIA container runtime for GPU and Argus.

### Runtime layout (compose)
- `hero_bringup` (launch)
- `hero_vision_capture`
- `hero_vision_perception`
- `hero_inputs`
- `hero_ui_bridge`
- `hero_telemetry`

### Jetson-specific mounts (typical)
- `/tmp/argus_socket:/tmp/argus_socket`
- `/dev:/dev` (or tighter: only needed devices)
- `--runtime nvidia` / `--gpus all` depending on setup

If capture is fragile in Docker, run capture on host and keep perception+UI in containers.

---

## Telemetry spec

Every node should expose:
- structured logs (stdout)
- metrics:
  - capture FPS, dropped frames
  - inference latency
  - queue depth/backpressure
  - CPU/GPU temps (system node)
- health heartbeat:
  - publish `/system/health` at 1 Hz with node status

---

## Bring-up sequence

### Milestone 1: Plumbing
1) Create `hero_interfaces` messages (FrameMeta, Detection, ButtonEvent, GestureEvent, Intent, AskRequest/Response).
2) `hero_bringup` launches:
   - `hero_inputs` (mock events ok)
   - `hero_ui_bridge` (basic buttons publish intents)
   - `hero_telemetry` (heartbeat + temps)
3) Verify with `ros2 topic echo` that events flow.

### Milestone 2: Camera
4) `hero_vision_capture` publishes `/camera/image` + `/camera/frame_meta`.
5) Verify live preview via `rqt_image_view` or a tiny subscriber node.
6) Record rosbag2 for 10 seconds, replay it.

### Milestone 3: First semantics
7) `hero_vision_perception` subscribes to camera, publishes `/vision/detections` and `/vision/scene_summary` (left/right).
8) `hero_behavior` prints interpreted summary (“chair right”).

### Milestone 4: Ask loop
9) Implement unknown trigger → publish `/ask/request`.
10) UI shows crop + lets user label → publish `/ask/response`.
11) Learning store persists labels.

### Milestone 5: Containers
12) Containerize non-hardware nodes first (UI, telemetry, behavior).
13) Containerize perception.
14) Containerize capture last (only if stable).

---

## Professional guardrails

- **Version the interfaces**: treat `hero_interfaces` as the API boundary.
- **No cross-imports between subsystems** except via interfaces/contracts.
- **Record everything** (at least meta + detections; full images during dev).
- **Feature flags**: detection/segmentation/ask loop togglable at runtime (`/vision/set_mode`).
- **Reproducibility**: pin model versions and keep a “models manifest” (hashes).
