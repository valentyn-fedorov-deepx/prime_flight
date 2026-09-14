"""Buffered single-pass decisions for GM v2 (ADR-002, opt-in): camera type and arrival without the second decode.

GM v1 (general_model @ a0157a4, and 8576299 which produced the monthly test set) decodes the whole video a second time to
decide two per-video report fields: `camera_type` / `confidence_camera` (EfficientNet-B0 cone/wing classifier on every
frame with the main aircraft once GM's own `Airplane` state machine has arrived; majority at the end) and `frame_stopped`
(that state machine's `arrival_frame`, MobileSAM masks + optical flow). The exact port (`pf.gm.second_pass`) costs about
24.5 ms/frame over the whole video (`tasks/notes/PF-Q1-16.md`).

This module replaces that pass with a bounded buffer filled inside the single GM v2 pass and decisions taken once
Tracker v2 has published T_ARR:

  during the pass   `CameraVoteBuffer`, attached as `GmStream.frame_observer`: on every `every_n_frames`-th frame
                    (`frame_id % 8 == 0`) that has a tracked aircraft, the v1 classifier (`pf.gm.camera.CameraClassifier`:
                    rows 150:930, PIL on the BGR array, Resize 224, ImageNet normalisation, sigmoid >= 0.5) runs on v1's
                    second-pass working frame; the buffer keeps (frame_id, probability, on the running main aircraft).
                    Voting starts at the first aircraft frame because arrival is not known inside GM. At the end of the
                    event `finalize()` marks every vote with the final main-aircraft membership (the frames that get a
                    class-2 row in the second-run file, v1's `max_time_plane_history`). Three numbers per vote, one vote
                    per second of aircraft presence (about 2 000 per turnaround).
  after Tracker v2  `decide_camera()`: the ADR-002 rule on the votes at frames >= T_ARR on the main aircraft — decide once
                    at least 50 votes are in and the running cone share is >= 0.9 (cone) or <= 0.1 (wing), otherwise the
                    v1 majority of the sampled votes at the end of the event. `frame_stopped` := T_ARR of Tracker v2 (its
                    first stopping frame; v1 GM reports the later frame on which its stop counter completes). The aircraft
                    type comes from the existing voters replayed over the recorded rows with the real arrival
                    (`replay_aircraft_type`).

Working frame. v1's second pass classifies `image_preprocessor.get_preprocessed()` once the main aircraft has been seen:
the same noise-adaptive preprocessing of the same decoded frame, with the same mode sequence, as the first pass, whose
result is the detector input. With detectors, `GmStream` hands the observer that exact array (the detectors upload a copy
and never write to it), so no frame is preprocessed twice. On the replay path (recorded rows, no detectors) the buffer
runs its own `ImagePreprocessor` on every frame and blurs only the voted frames (`pf.gm.second_pass.preprocess_frame`,
the same OpenCV calls). v1 classifies the raw frame on frames up to its first class-2 frame; those frames lie before
arrival (the stop alone takes more than 4 s), so they never count.

No image ring buffer. The classifier input of frame f depends only on frame f and on the noise mode in force at f, both
known while f is processed; the late T_ARR (Tracker v2 publishes it only after its stop counter, several seconds after
the frame it reports) merely selects votes that are already stored. A ring buffer of frames would be needed only if
voting started at arrival. The aircraft-type replay needs rows, which `GmStream` keeps anyway (`raw_rows`).
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from pf.gm.camera import CAMERA_WEIGHTS, CROP_ROWS, majority_vote

EVERY_N_FRAMES = 8
BUFFER_VERSION = 1


# ---------------------------------------------------------------- votes collected during the pass


@dataclass
class CameraVote:
    frame_id: int
    prob: float  # sigmoid output: the float32 value as a Python float (JSON round-trips it exactly)
    main_running: bool  # the frame is on the longest aircraft track known on that frame (causal)
    main_final: bool | None = None  # the frame is on the final main-aircraft track (class-2 row in the second-run file)

    @property
    def is_cone(self) -> bool:
        return self.prob >= 0.5  # v1: `outputs >= 0.5` on the float32 tensor; float32 -> float is exact


class CameraVoteBuffer:
    """`GmStream.frame_observer` that collects sampled camera votes during the single GM v2 pass (see the module docstring).

    Use one buffer per event and one kind of stream: with detectors (the detector input is reused) or on the replay path
    (own preprocessor updated on every frame)."""

    def __init__(self, classifier, every_n_frames: int = EVERY_N_FRAMES, noise_fn=None):
        """`classifier`: an object with `predict(frame_bgr) -> (is_cone, probability)` (`pf.gm.camera.CameraClassifier`).
        `noise_fn`: noise estimate of the own preprocessor on the replay path (default: scikit-image, as v1)."""
        if every_n_frames < 1:
            raise ValueError("every_n_frames must be >= 1")
        self.classifier = classifier
        self.every_n_frames = int(every_n_frames)
        self.noise_fn = noise_fn
        self.pre = None  # own ImagePreprocessor, created on the first frame that arrives without a detector input
        self.votes: list[CameraVote] = []
        self.finalized = False
        self.frames_observed = 0
        self.saw_detector_input = False
        self.own_blurred_votes = 0
        self.observe_s = 0.0
        self.classifier_s = 0.0
        self.noise_s = 0.0
        self.blur_s = 0.0
        self.call_ms: list[float] = []  # wall time of each classifier call (the first one includes CUDA warm-up)

    def _own_preprocessor(self):
        if self.pre is None:
            from pf.gm.preprocessor import ImagePreprocessor, estimate_noise

            self.pre = ImagePreprocessor(noise_fn=self.noise_fn or estimate_noise)
        return self.pre

    def observe(self, frame_id: int, image, aircraft, detector_input=None) -> CameraVote | None:
        """Called by `GmStream` after the context update of `frame_id`.

        `image`: the decoded BGR frame (None: nothing to classify); `aircraft`: the context's main-aircraft tracker
        (`tracks`, `longest()`); `detector_input`: the preprocessed frame the detectors received, None on the replay path.
        """
        t0 = time.perf_counter()
        self.frames_observed += 1
        if detector_input is not None:
            self.saw_detector_input = True
        elif image is not None:
            tn = time.perf_counter()
            self._own_preprocessor().update(frame_id, image)  # v1 updates its preprocessor on every frame
            self.noise_s += time.perf_counter() - tn
        vote = None
        if image is not None and frame_id % self.every_n_frames == 0:
            tracks = aircraft.tracks
            if any(frame_id in frames for frames in tracks.values()):
                tid = aircraft.longest()
                running = tid is not None and frame_id in tracks[tid]
                if detector_input is not None:
                    work = detector_input
                else:
                    from pf.gm.second_pass import preprocess_frame

                    tb = time.perf_counter()
                    work = preprocess_frame(image, self.pre.mode)
                    self.blur_s += time.perf_counter() - tb
                    if work is not image:
                        self.own_blurred_votes += 1
                tc = time.perf_counter()
                _is_cone, prob = self.classifier.predict(work)
                dt = time.perf_counter() - tc
                self.classifier_s += dt
                self.call_ms.append(1000 * dt)
                vote = CameraVote(int(frame_id), float(prob), bool(running))
                self.votes.append(vote)
        self.observe_s += time.perf_counter() - t0
        return vote

    def finalize(self, main_history) -> None:
        """Mark the final main-aircraft membership. `main_history`: {frame_id: box} of the longest track at the end of the
        event (`VideoContextV2.aircraft.snapshot()["history"]` — exactly the frames with a class-2 row in the second run)."""
        history = main_history or {}
        for v in self.votes:
            v.main_final = v.frame_id in history
        self.finalized = True

    def as_report(self, *, aircraft=None, variant: str | None = None) -> dict:
        """The `buffered_votes` report field (inverse: `votes_from_report`)."""
        first = None
        if aircraft is not None:
            first = getattr(aircraft, "first_track_at", None) or getattr(aircraft, "first_seen_at", None)
        return {
            "version": BUFFER_VERSION,
            "every_n_frames": self.every_n_frames,
            "variant": variant,
            "classifier": {"weights": CAMERA_WEIGHTS, "crop_rows": list(CROP_ROWS), "cone_if_prob_at_least": 0.5,
                           "transform": getattr(self.classifier, "transform", None)},
            "working_frame": "detector_input" if self.saw_detector_input else "own_preprocessor",
            "first_aircraft_track_frame": first,
            "votes": len(self.votes),
            "frames": [v.frame_id for v in self.votes],
            "probs": [v.prob for v in self.votes],
            "main_running": [int(v.main_running) for v in self.votes],
            "main_final": [int(bool(v.main_final)) for v in self.votes] if self.finalized else None,
        }

    def cost_ms_per_frame(self, frames: int | None = None, init_s: float = 0.0) -> dict:
        """Added cost over `frames` frames (default: the frames observed). `own_noise_estimate` / `own_blur` are zero with
        detectors (the detector input is reused) and are the replay path's own preprocessing otherwise."""
        n = max(int(frames or self.frames_observed), 1)
        gating = self.observe_s - self.classifier_s - self.noise_s - self.blur_s
        return {
            "frames": n,
            "classifier_calls": len(self.votes),
            "total": round(1000 * self.observe_s / n, 3),
            "classifier": round(1000 * self.classifier_s / n, 3),
            "own_noise_estimate": round(1000 * self.noise_s / n, 3),
            "own_blur": round(1000 * self.blur_s / n, 3),
            "gating": round(1000 * gating / n, 3),
            "ms_per_classifier_call": round(1000 * self.classifier_s / len(self.votes), 3) if self.votes else None,
            "classifier_call_ms": _distribution(self.call_ms),
            "classifier_split_ms_per_call": _classifier_split(self.classifier),
            "init_s": round(init_s, 2),
        }


def _distribution(values) -> dict | None:
    if not values:
        return None
    s = sorted(values)

    def pick(q):
        return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]

    rest = values[1:]
    return {"calls": len(values), "first": round(values[0], 2), "p50": round(pick(0.5), 2), "p90": round(pick(0.9), 2),
            "max": round(s[-1], 2), "mean_without_first": round(sum(rest) / len(rest), 2) if rest else None}


def _classifier_split(classifier) -> dict | None:
    calls = getattr(classifier, "calls", 0)
    if not calls or not hasattr(classifier, "prep_s"):
        return None
    return {"cpu_crop_pil_transforms": round(1000 * classifier.prep_s / calls, 2),
            "gpu_upload_forward_sync": round(1000 * classifier.gpu_s / calls, 2)}


def votes_from_report(buffered: dict) -> list[CameraVote]:
    """Votes from the `buffered_votes` field of a GM v2 report."""
    frames, probs, running = buffered["frames"], buffered["probs"], buffered["main_running"]
    final = buffered.get("main_final")
    if final is None:
        final = [None] * len(frames)
    if not len(frames) == len(probs) == len(running) == len(final):
        raise ValueError("buffered_votes: arrays of different lengths")
    return [
        CameraVote(int(f), float(p), bool(r), None if m is None else bool(m))
        for f, p, r, m in zip(frames, probs, running, final)
    ]


# ---------------------------------------------------------------- decisions after Tracker v2


@dataclass(frozen=True)
class CameraRule:
    """ADR-002 §2: the sampled, early camera decision."""

    min_votes: int = 50
    cone_share_hi: float = 0.9
    cone_share_lo: float = 0.1


@dataclass
class CameraDecision:
    camera_type_cone: bool | None  # the report's `camera_type` (True = cone)
    confidence_camera: float  # share of the counted votes for the decided side (v1 semantics on the sampled votes)
    decided_at: int | None  # frame on which the decision can be emitted
    rule: str  # 'share' | 'end_majority' | 'no_votes' | 'no_arrival'
    votes_used: int  # counted votes the decision rests on
    cone_share: float | None  # cone share of those votes
    fired_on_vote_frame: int | None  # frame of the last vote the 'share' rule saw
    membership: str  # 'final' (v1 class-2 frames) or 'running' (causal)
    t_arr: int | None
    t_arr_known_at: int | None
    votes_after_arrival: int  # all counted votes until the end of the event
    cone_share_all_votes: float | None
    end_majority_cone: bool | None  # v1 majority over all counted votes (what the 'end' rule would say)
    end_majority_confidence: float

    def as_dict(self) -> dict:
        return asdict(self)


def decide_camera(
    votes,
    t_arr: int | None,
    *,
    t_arr_known_at: int | None = None,
    end_frame: int | None = None,
    rule: CameraRule = CameraRule(),
    membership: str = "final",
) -> CameraDecision:
    """ADR-002 camera decision on buffered votes.

    Counted votes: frame >= `t_arr` (Tracker v2 T_ARR frame) and on the main aircraft — `membership` 'final' uses the final
    main-aircraft track (v1's class-2 frames, known at the end of the event), 'running' the longest track known on the
    vote's own frame (causal). The rule is evaluated causally: nothing is decided before T_ARR is published
    (`t_arr_known_at`, the frame whose tracker record first carried it; default `t_arr`); at that frame every stored vote
    from `t_arr` on counts at once, afterwards the rule is re-evaluated after each new vote. It fires on the first evaluation
    with at least `min_votes` votes and a cone share >= `cone_share_hi` (cone) or <= `cone_share_lo` (wing); confidence =
    the share of the decided side. If it never fires, the v1 majority of all counted votes decides at `end_frame` (a tie is
    wing, and no votes give (None, 1.0), as in v1).
    """
    if membership not in ("final", "running"):
        raise ValueError(f"membership must be 'final' or 'running', not {membership!r}")
    if t_arr is None:
        return CameraDecision(None, 1.0, end_frame, "no_arrival", 0, None, None, membership, None, None, 0, None, None, 1.0)
    t_arr = int(t_arr)
    known = t_arr if t_arr_known_at is None else max(int(t_arr_known_at), t_arr)

    def member(v: CameraVote) -> bool:
        if membership == "running":
            return v.main_running
        if v.main_final is None:
            raise ValueError("votes carry no final main-aircraft membership (CameraVoteBuffer.finalize was not called)")
        return v.main_final

    counted = sorted((v for v in votes if v.frame_id >= t_arr and member(v)), key=lambda v: v.frame_id)
    n = len(counted)
    end_cone, end_conf = majority_vote([v.is_cone for v in counted])
    share_all = (sum(v.is_cone for v in counted) / n) if n else None
    cone = 0
    for k, v in enumerate(counted, 1):
        cone += v.is_cone
        if v.frame_id <= known and k < n and counted[k].frame_id <= known:
            continue  # T_ARR not published yet: the first evaluation sees every vote stored up to `known`
        if k >= rule.min_votes:
            share = cone / k
            if share >= rule.cone_share_hi or share <= rule.cone_share_lo:
                is_cone = share >= rule.cone_share_hi
                return CameraDecision(
                    is_cone, share if is_cone else 1 - share, max(v.frame_id, known), "share", k, share, v.frame_id,
                    membership, t_arr, known, n, share_all, end_cone, end_conf,
                )
    if not n:
        return CameraDecision(None, 1.0, end_frame, "no_votes", 0, None, None, membership, t_arr, known, 0, None, None, 1.0)
    return CameraDecision(
        end_cone, end_conf, end_frame, "end_majority", n, share_all, None, membership, t_arr, known, n, share_all, end_cone,
        end_conf,
    )


def replay_aircraft_type(frames, cm, *, variant: str, t_arr: int | None, t_dep: int | None = None, fps: int = 8) -> dict:
    """The existing aircraft-type voters fed with the real arrival (Tracker v2) instead of GM's placeholder flags.

    `frames`: iterable of (frame_id, first-run rows, main-aircraft box or None) in frame order; the box is the class-2 row
    of the second-run file (v1's `max_time_plane_history[frame]`).
      * 'entity_clip' / 'master' (8576299 / 13a4ddc `main.py` second pass): on frames with the main aircraft at or after
        T_ARR, `aircraft_determining(first-run rows)` (`AircraftTypeVoter`) until one type has more than 500 votes; v1 copies
        the answer into the report on the next such frame (kept here); no answer → None.
      * 'prod' (a0157a4): `AircraftTypeVoterProd` on every frame (main-aircraft presence, the last main box,
        arrived = frame >= T_ARR, departured = frame >= T_DEP); the answer at T_DEP or at the end of the event.
    Semantics difference: v1 gates on GM's own arrival, which completes later than the tracker's T_ARR frame.
    """
    from pf.gm.context import AircraftTypeVoter
    from pf.gm.context_prod import AircraftTypeVoterProd

    if variant == "prod":
        voter = AircraftTypeVoterProd(fps=fps)
        last_frame, last_box = None, None
        for frame_id, rows, box in frames:
            last_frame = frame_id
            if box is not None:
                last_box = box
            voter.feed(
                frame_id,
                rows,
                cm,
                plane_available=box is not None,
                main_plane_xyxy=last_box,
                arrived=t_arr is not None and frame_id >= t_arr,
                departured=t_dep is not None and frame_id >= t_dep,
            )
        if last_frame is not None:
            voter.finalize(last_frame)
        answer = None if voter.answer == "not evaluated" else voter.answer
        return {"airplane_type": answer, "decided_at": voter.decided_at, "voter": "AircraftTypeVoterProd",
                "counters": dict(voter.counters)}

    voter = AircraftTypeVoter()
    reported, reported_at, fed = None, None, 0
    for frame_id, rows, box in frames:
        if box is None or t_arr is None or frame_id < t_arr:
            continue
        if voter.answer is None:
            voter.feed(frame_id, rows, cm)
            fed += 1
        elif reported is None:
            reported, reported_at = voter.answer, frame_id
    return {"airplane_type": reported, "decided_at": reported_at, "answer_reached_at": voter.decided_at,
            "voter": "AircraftTypeVoter", "frames_fed": fed,
            "votes": {str(k): v for k, v in voter.votes.items() if k != "answer"}}
