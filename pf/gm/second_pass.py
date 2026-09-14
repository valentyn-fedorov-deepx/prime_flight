"""GM second pass — the per-frame decisions of general_model @a0157a4 that need the decoded (noise-preprocessed) frames
and the main-aircraft track: the aircraft's motion state (arrived / departed → `frame_stopped`) and the camera-type vote.

Source: `main.py:762-947` (loop), `:956-963` (majority), `:1117-1126` (confidence, report fields). The report fields
`camera_type`, `confidence_camera` and `frame_stopped` are what `db_worker/model_starter.py` hands to the modules.

Input per frame: the decoded BGR frame and the SECOND-RUN rows of that frame. The class-2 row is v1's
`max_time_plane_history[frame]` (box + mode height in the conf slot); person / trailer / fuel_truck / gse boxes are removed
from the aircraft's optical flow (`worker_bboxes`); airplane_nose boxes seed the segmentation points.

v1 order kept per frame: `ImagePreprocessor.update(raw)`; once an aircraft object exists the pass works on the preprocessed
frame; the Plane is created on the first class-2 frame and updated on the next ones with MobileSAM; `frame_stopped` follows
`arrival_frame` while arrived; `prev_im0s` is the working frame of every frame; one camera vote per frame with the aircraft
after arrival.

Deviation (tasks/notes/PF-Q1-16.md): GM's cv_common pin d74eb096 is not in the local archive, so the Airplane /
TrackedObject classes are the vendored 2759daf ones with the MobileSAM segmenter (the ac5098d2 code path); 2759daf repairs
out-of-frame boxes where ac5098d2 raised.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

REMOVE_CLASSES = ("person", "trailer", "fuel_truck", "gse")


@dataclass
class SecondPassResult:
    camera_type_cone: bool | None
    confidence_camera: float
    frame_stopped: int | None
    first_plane_frame: int | None
    first_frame_with_arrived: int | None
    departure_frame: int | None
    camera_votes: int
    plane_frames: int

    def as_dict(self) -> dict:
        return asdict(self)


class SecondPass:
    def __init__(self, cfg: dict, weights_dir: str, device: str = "cuda:0", noise_fn=None, predictor=None, camera="load"):
        """`predictor` / `camera` can be injected (tests, shared models); by default MobileSAM and the camera classifier are
        loaded from `weights_dir` (`mobile_sam.pt`, `camera_cls_effnet_b0_october_v1.8.1.pt`). `camera=None` disables votes."""
        from pf.gm.preprocessor import ImagePreprocessor, estimate_noise

        s2i = cfg["str2id"]
        self.cfg = cfg
        self.airplane_id = s2i["airplane"]
        self.nose_id = s2i["airplane_nose"]
        self.remove_ids = {s2i[c] for c in REMOVE_CLASSES}
        self.plane_params = cfg["tracking"]["airplane"]["tracked_object"]
        if predictor is None:
            from mobile_sam import SamPredictor, sam_model_registry

            sam = sam_model_registry["vit_t"](checkpoint=os.path.join(weights_dir, "mobile_sam.pt"))
            sam.to(device=device)
            sam.eval()
            predictor = SamPredictor(sam)
        self.predictor = predictor
        if camera == "load":
            from pf.gm.camera import CameraClassifier

            camera = CameraClassifier(weights_dir, device=device)
        self.camera = camera
        self.pre = ImagePreprocessor(noise_fn=noise_fn or estimate_noise)
        self.main_plane = None
        self.airplane_detected = False
        self.prev_im0s = None
        self.frame_stopped = None
        self.first_arrived_frame = None
        self.departure_frame = None
        self.first_plane_frame = None
        self.plane_frames = 0
        self.votes: list = []
        self.probs: list = []

    def parse_rows(self, rows) -> tuple:
        nose_list, bboxes_to_remove, largest_plane, mode_height = [], [], None, None
        for *xyxy, conf, cls_id in rows or []:
            cls_id = int(cls_id)
            box = list(map(int, xyxy))
            if cls_id == self.airplane_id:
                largest_plane, mode_height = box, int(conf)
                continue
            if cls_id == self.nose_id:
                nose_list.append(box)
            if cls_id in self.remove_ids:
                bboxes_to_remove.append(box)
        return largest_plane, mode_height, nose_list, bboxes_to_remove

    def update(self, frame_id: int, frame_bgr, rows) -> None:
        from pf.tracker._v1 import tracked_object as to_mod
        from pf.tracker._v1.transport import Airplane

        im0s = frame_bgr
        self.pre.update(frame_id, im0s)
        if self.airplane_detected:
            im0s = self.pre.get_preprocessed()
        largest_plane, mode_height, nose_list, bboxes_to_remove = self.parse_rows(rows)

        plane_available = largest_plane is not None
        if plane_available:
            self.plane_frames += 1
            if self.main_plane is None:
                self.main_plane = Airplane(obj_id=0, xyxy=largest_plane, tracking_params=dict(self.plane_params),
                                           height_mode=mode_height)
                # v1 GM (cv_common before YOLO-seg): MobileSAM segmentation of the aircraft
                self.main_plane._TrackedObject__segmenter = to_mod.ObjectSegmenter(model_type="mobile_sam")
                self.first_plane_frame = frame_id
            else:
                self.main_plane.update_params(largest_plane, self.prev_im0s, im0s, frame_id, self.predictor, nose_list,
                                              bboxes_to_remove=bboxes_to_remove)
            self.airplane_detected = True

        mp = self.main_plane
        if mp is not None and mp.arrived:
            self.frame_stopped = mp.arrival_frame
            if self.first_arrived_frame is None:
                self.first_arrived_frame = frame_id
        if mp is not None and mp.departured and self.departure_frame is None:
            self.departure_frame = mp.departure_frame

        self.prev_im0s = im0s.copy()

        if plane_available and mp.arrived and self.camera is not None:
            is_cone, p = self.camera.predict(im0s)
            self.votes.append(is_cone)
            self.probs.append(p)

    def result(self) -> SecondPassResult:
        from pf.gm.camera import majority_vote

        cone, confidence = majority_vote(self.votes)
        return SecondPassResult(
            camera_type_cone=cone,
            confidence_camera=confidence,
            frame_stopped=self.frame_stopped,
            first_plane_frame=self.first_plane_frame,
            first_frame_with_arrived=self.first_arrived_frame,
            departure_frame=self.departure_frame,
            camera_votes=len(self.votes),
            plane_frames=self.plane_frames,
        )
