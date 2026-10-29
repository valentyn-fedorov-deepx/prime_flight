# Handrails on GSE being used

*In plain words: handrails on service vehicles being used.*

> This check is about the belt loader, a service vehicle (ground support equipment, like tugs, fuel trucks and
> tractors) with a conveyor that carries bags up to a cargo door: every worker who walks up it must hold the handrail.
> The software finds the stopped belt loader at the camera's door, checks that its handrails are extended, follows each
> worker with a whole-body pose model that also finds the hands, and looks for a hand on the rail.

## Status

| | |
|---|---|
| How accurate it is | 51 of 56 turnarounds correct (91 %) on the monthly test |
| Fail turnarounds it caught | 41 of 45 |
| In production | the version of July 2026 |
| Who looks after it | to assign |
| Biggest open problem | The patch check credits a hand on the rail to every worker seen in the last 2.5 seconds, so a worker who does not hold the rail can pass with a colleague. |

## What the client wants

*Handrails on GSE being used* (GSE: ground support equipment)

| Verdict | When |
|---|---|
| Pass | Every worker seen on the belt loader touched the handrail while walking. The handrails are extended and no significant obstacle prevents the check. |
| Fail | At least one worker on the belt loader did not touch the handrail while walking, or the handrail was not used consistently over the frames in which the worker is seen. |
| Not observed | No belt loader is found, or no worker walks on it — for example because of poor visibility, something in the way, or the camera angle. |
| Not observed, view blocked | Handrail use cannot be confirmed because more than 80 % of the belt loader is hidden. |

A verdict is the answer of a check: Pass, Fail or Not observed. A frame is one picture of the video; the cameras take 8
per second.

## When and where it looks

Unloading and loading (a stage is a part of the turnaround): from the moment the tracker reports the aircraft as arrived
until its departure, only on frames in which the belt loader at this camera's door is stopped. For aircraft, the cone
camera (looks towards the aircraft nose) watches the front belt loader and the wing camera (looks along the wing) the
back one. Not used for jets.

## What it looks at

- **From the General Model** (the shared detector; a detection is a box it draws around an object): people, the front
  and back cargo doors, engines, the aircraft's rear wheels.
- **From the tracker** (a track is the same object followed from frame to frame): the aircraft (arrived, departed, its
  box), belt loaders (the door each serves, stopped or not) and people.
- **From the video itself:** yes, every frame, for the four models below.
- **Its own models:**
  - **handrail classifier** (trained by us): "handrails extended" or not; *Safety handrails fully extended and used*
    uses the same model.
  - **handrail segmentation** (trained by us): marks, pixel by pixel, where the rail is; its top edge gives the rail line.
  - **hand-contact classifier** (trained by us): says whether a hand is on the rail in a small square of the picture.
  - **whole-body pose model** (standard, not trained by us): finds the body points (nose, eyes, ears, shoulders,
    elbows, wrists, hips, knees, ankles), the feet, the face and 21 points on each hand (wrist and finger joints). The
    module uses the hand points, and the ankles to know the whole person is seen.

## How it decides, step by step

1. **Window.** It starts at the aircraft's arrival. It ends at the tracker's departure if the aircraft box, between the
   first and the last 3 seconds of its movement, shrank by more than 18 % (the aircraft moves away); otherwise it reads
   to the end of the video.
2. **Belt loader.** The one the tracker labelled for this door (front on the cone camera, back on the wing camera). If
   none: on the wing camera one under the engine or face-on under the back door; on the cone camera one at least 70 %
   inside the aircraft box, 13–55 % of the aircraft's height and lined up with the front door. The biggest wins; frames
   in which it is not stopped are skipped. Its box is raised by 30 % of its height to take in the rails.
3. **Handrails.** On each such frame the classifier says extended or not; if extended, the segmentation gives the rail
   line. On the wing camera the view is also classed as face-on (under the door) or "left side" (belt loader to the
   right of the back door), which has its own thresholds and no patch check.
4. **Workers.** Tracked people inside the belt loader box — feet above its lowest 20 %, taller than 20 % of it (face-on:
   also near its middle) — are workers on it. Frames where an ankle point is uncertain (score under 0.3) or the size is
   implausible do not count for coverage.
5. **Touch, by pose.** It takes the centre of the hand on the rail side (cone camera: from where the head turns; wing
   camera: from the shoulders). Within a few pixels of the rail line (about 1/60 of the belt loader's height, 1/30
   left side) for 5 frames in a row (4 left side): touch confirmed.
6. **Touch, by patch check.** Patches along the whole rail go to the hand-contact classifier. Two positive frames in a
   row confirm a touch for every worker seen on the belt loader in the last 20 frames (2.5 seconds); a worker seen later
   also gets them. On the side view, someone climbing the side stairs at the right end (3 rising sightings within 2
   seconds) needs only one positive frame. With the rails not extended, neither touch check runs.
7. **Coverage.** At the end of the video: how much of the rail's length each worker's box passed along. Without any rail
   mask the belt loader's width (less 5 % at each end) stands in; face-on, the worker's travel upwards against 30 % of
   the belt loader's height.
8. **Each worker:** touch and coverage above 25 % → Pass; no touch and coverage above 30 % (40 % left side) → Fail;
   otherwise not judged.
9. **Verdict:** no belt loader, or no judged worker → Not observed; any failed worker → Fail; otherwise Pass.

## Settings that change the result

| Setting | Value | What it changes |
|---|---|---|
| Departure confirmation | aircraft box shrinks by more than 18 % | Ends the window |
| Coverage | above 25 % for Pass; above 30 % for Fail (40 % left side) | Fixed in the code |
| Touch by pose | 5 frames (4 left side); about 1/60 of the height (1/30 left side) | Fixed in the code |
| Patch check | 2 positive frames (1 after the stairs); memory 20 frames (2.5 seconds) | Fixed in the code |
| Obstacle area; "camera type does not matter" | width 30 %, centre at 30–100 % of the picture; off | Not used by the code |

## What it reports

- **Sentence:** "All workers touched the handrail while walking on the beltloader." (or "Not all workers…"), then the
  number, Pass or Fail and time of each judged worker. Not observed: no belt loader was detected, or no worker walking
  on it ("Possible obstruction or poor camera angle.").
- **Timeline entry:** one Pass or Fail block per judged worker, from the first to the last frame on the belt loader.
- **Files:** a drawing file for every frame; an annotated video on request.

## How accurate it is

The monthly test is the client's validated turnarounds we measure on: 69 turnarounds, 56 labelled for this check. The
module matched the client on 51 (91 %) and caught 41 of the 45 labelled Fail, so 4 of its 5 errors are missed
violations. With this many Fail labels the test does show that it catches most violations; whether the patch check
causes the misses: not known yet.

## Known problems

- **No "view blocked" verdict.** Obstacles (trailers, service vehicles, people taller than 60 % of the picture) are
  collected but unused and the obstacle settings have no effect, so Not observed comes only when no worker is judged,
  not when 80 % of the belt loader is hidden.
- **The patch check is not tied to a person.** A hand on the rail counts for every worker seen in the last 2.5 seconds,
  though the rule asks each worker to touch; one who does not hold the rail can pass with a colleague.
- **Retracted handrails.** No touch is possible, so a worker who walks far enough fails; the rule's Pass needs extended
  rails but is silent on the other case. Whether Fail is intended: to confirm.
- **One belt loader per camera** (the biggest at the door); workers are never reset between belt loader visits.
- **Start-up download:** unlike the default line, production first downloads general starting weights for the
  hand-contact classifier from the internet, before loading ours.
- **The heaviest module per frame.** It reads every frame from the first; the pose model runs once per worker, one at a
  time, and gets its colour channels in reverse order (effect to confirm).
- **Wing-camera door label (to confirm):** production may not tell the tracker the camera (no back-door label in 7
  sample videos); the wing camera would then rely on step 2's fallbacks.

## In real time

It runs unchanged but needs the pictures: four models on every frame with a stopped belt loader. Coverage is final only
at the end, so the verdict comes when the recording ends; in the real-time test setup, on a 36-minute turnaround, it
matched post-processing (Fail).

Own work: about 12.5 milliseconds per frame (17.9 with all checks together); with the shared General Model and tracker
parts, 47.0 of the 125 milliseconds each frame may take (38 %), on a faster graphics card than production's; as a
post-processing job about 249 seconds. Lighter, same results: read pictures only once the aircraft has arrived and a
belt loader is found, share the handrail classifier with the extended-handrails check, batch the pose model. It needs
"a belt loader reached the door" from the stage detector (which knows where in the turnaround we are).

## For developers

- **Repository:** `dxgat/detectors/handrails-on-gse-being-used`; production `per_component_improvement` @ `f2c4793`
  (2026-07-09); default `master` @ `59fbced` (2026-04-10: no cone-camera fallback, no stairs logic, older departure
  check, no crash guards; has the `pretrained=False` fix). Workspace module code: M14.
- **Entry point:** `main.py` → `detect(...)`; classes `Airplane`, `Loader`, `Climber`, verdict `make_inference`.
- **Models (DVC):** handrail EfficientNet-B0
  `efficientNetb0_300_epoch_general_classifier_dataset_safety_handrails_v3_26_09_2023.pth`; Unet MiT-B0
  `safety_handrails_mit_b0_best_model_293_epoch_30_10_2023.pth`; hand contact EfficientNet-B0
  `effnetb0_weighted_norm_aug_929.pt` (`pretrained=True` at `local_models/efficientnet_reg.py:16`); DWPose-l
  `dw-ll_ucoco_384.onnx`, CUDA only (GPU needed). `cv_common` @ `33c188d`, `db_worker` @ `5a4aa83`.
- **Run:** `python main.py --source <video.mp4> --inferences-dir <dir> --weights-dir weights [--cone-camera]
  [--write-video] [--debug]`.
- **Settings keys:** `departure_bbox_change`; `cone.obstacle`, `wing.obstacle`, `camera_type_irrelevant` (unused);
  coverage `main.py:623-627`; pose touch `main.py:488-523`; patch check `main.py:659-704, 870`; box raise `main.py:149`.
- **Code places:** step 1 `main.py:911-941`; 2 `main.py:145-150, 986-1056`; 3 `main.py:1058-1110, 167-191`; 4
  `main.py:1180-1215, 423-449`; 5 `main.py:452-531`; 6 `main.py:1124-1178, 633-704, 1232-1235`, stairs
  `main.py:194-268, 1196-1207`; 7 `main.py:534-627, 1243-1245`; 8-9 `main.py:64-112`.
