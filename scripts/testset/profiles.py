"""How each production module is launched locally for the test-set run (environment facts, not module semantics).

Every entry is a measured requirement of the module code on this machine (Python 3.11, torch 2.11 cu128, NumPy 2.x, norfair 2.3):
  * device       — YOLOv5 `select_device` in wing-walkers accepts only a bare index;
  * numpy1       — `float(one-element array)` calls that NumPy 2 rejects (see scripts/run_module.py --numpy1-scalars);
  * prepend_path — folders put before site-packages (pinned pure-Python packages, e.g. norfair 0.3.1);
  * drop_state_keys — tracker state keys the module's cv_common copy rejects and the module never reads;
  * pixel_free   — never reads frames; may run with --no-video once the video was cleaned up;
  * launcher     — argv that replaces `python scripts/run_module.py` (another runtime, e.g. WSL); paths are then passed
                   relative to the repository root with forward slashes;
  * job_class    — orchestrator concurrency class (default: `mod` for pixel-free modules, `mod_gpu` otherwise);
  * module_dir   — module checkout relative to the repository root when not `external/<module>` (branch exports in
                   `external/_branches/<module>@<branch>`, marker `PF_SOURCE.txt`); results from another checkout are redone.
Modules whose environment is not ready are listed in the orchestrator control file (`disabled_modules`), not here.
"""

from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PIXEL_FREE = {
    "3-stop-brake-check",
    "all-cargo-bin-doors-opened-and-verified",
    "beltloader-chocks",
    "bl_rear_cone",
    "chocks-and-cones-available-and-staged-for-arrival",
    "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked",
    "cones-placed-in-proper-positions-and-timely",
    "crew-present-10-minutes-prior-to-aircraft-arrival",
    # lead-marshaller-and-wing-walkers-in-position: pixel-free on the default branch, but the calibrated
    # pre_arrival_departure branch runs an mmpose model on frames -> GPU job class
    "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready",
    "pushback-pathway-confirmed-clear-of-obstacles",
}

NUMPY1 = {
    "lead-marshaller-and-wing-walkers-in-position",
    "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready",
    "wing-walkers-in-proper-position-and-using-approved-wands",
    "safety-zone-confirmed-clear",  # "only 0-dimensional arrays can be converted to Python scalars"
}

DEVICE = {
    "wing-walkers-in-proper-position-and-using-approved-wands": "0",
    "hair-policy": "cpu",  # Pyarmor build loads only on CPython 3.8; no torch for 3.8 supports sm_120
}

PREPEND_PATH = {
    # pre-departure: the default branch needed out/envs/norfair031 (norfair 0.3.1 API); the calibrated tdv_cone branch runs
    # in the np1_walkaround venv with its own norfair 2.2 (LAUNCHER below)
    # mmpose 1.x API: out/envs/mmpose1 (mmpose 1.3.1, mmcv-lite 2.1.0, mmengine 0.10.4, mmdet 3.2.0; README inside)
    "hand-signals": ["out/envs/mmpose1"],
    "steering-by-pass-pin-installed-or-steering-otherwise-bypassed": ["out/envs/mmpose1"],
    "pin-verification": ["out/envs/mmpose1"],
    # pre_arrival_departure branch: imbalanced-learn 0.13.0 + scikit-learn 1.6.1 (its pickled classifiers), mmpose 1.x
    "lead-marshaller-and-wing-walkers-in-position": ["out/envs/sklearn161", "out/envs/mmpose1"],
    # obstruction_hand_signals branch imports the mmpose 1.x API (the default branch does not import mmpose)
    "wing-walkers-in-proper-position-and-using-approved-wands": ["out/envs/mmpose1"],
}

# keys of the production tracker files (bd43c3c) that an older cv_common TrackedObject.from_state_dict rejects: the stage
# fields of transport.Airplane and the beltloader-type evidence on beltloader / gse records (scan of a full tracker file)
AIRPLANE_STAGE_KEYS = "_moving_counter,_stopped_counter,have_pre_arrival_stage,have_arrival_stage,departure_frame,_height_mode"
BL_TYPE_KEYS = "_bl_type_bbox,_bl_type_frames"
DROP_STATE_KEYS = {
    "post-arrival-aircraft-walk-around-inspection-completed-accurately": AIRPLANE_STAGE_KEYS + "," + BL_TYPE_KEYS,
    "pre-departure-walk-around-completed": AIRPLANE_STAGE_KEYS + "," + BL_TYPE_KEYS,
}

ENV = {
    "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD": "1",
    # ultralytics otherwise runs `pip install <missing package>` (e.g. lap for YOLO.track) into whatever interpreter
    # is on PATH, i.e. the shared global one
    "YOLO_AUTOINSTALL": "False",
}

# hair-policy: CPython 3.8 venv in WSL Ubuntu-24.04 (scripts/testset/wsl_run_module.sh picks it from the Pyarmor header)
_NP1_WALKAROUND = os.path.join(ROOT, "out", "envs", "np1_walkaround", "Scripts", "python.exe")
LAUNCHER = {
    "hair-policy": ["wsl", "-d", "Ubuntu-24.04", "--exec", "bash", "/mnt/g/prime_flight/scripts/testset/wsl_run_module.sh"],
    # walk-around tdv_cone branches: NumPy 1.26 + TensorFlow 2.15 venv (out/envs/np1_walkaround/README.md); pre-departure
    # loads its Keras-3 archive through the branch's own torch shim (single_run.py hook)
    "post-arrival-aircraft-walk-around-inspection-completed-accurately": [_NP1_WALKAROUND, "scripts/run_module.py"],
    "pre-departure-walk-around-completed": [_NP1_WALKAROUND, "scripts/run_module.py", "--keras-torch-shim"],
}

JOB_CLASS = {"hair-policy": "mod_cpu"}  # ~0.9 CPU-s per frame on 2 threads

# chosen by scripts/testset/calibrate.py against the report's New output (out/testset/calibration*.json)
MODULE_DIR = {
    # 8/8 events = New output (default branch 3/8)
    "cones-placed-in-proper-positions-and-timely": "external/_branches/cones-placed-in-proper-positions-and-timely@not_observed_logic",
    # 8/8 events = New output (default branch 5/8)
    "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready":
        "external/_branches/pushback-does-not-start-until-wing-walkers-are-in-place-and-ready@obstruction_plane_track",
    # ties with the default branch on 8/8 events; the branch carries the production fixes ("Fix prod issue ...") and the
    # new pre-arrival absence logic (needs cv_common/modules, overlaid from the archive @2759daf, PF_MODULES_OVERLAY.txt)
    "all-cargo-bin-doors-opened-and-verified": "external/_branches/all-cargo-bin-doors-opened-and-verified@bl_approach",
    "chocks-and-cones-available-and-staged-for-arrival":
        "external/_branches/chocks-and-cones-available-and-staged-for-arrival@not_observed_logic",
    # 8/8 events = New output (default branch 5/8); needs out/envs/sklearn161 + out/envs/mmpose1
    "lead-marshaller-and-wing-walkers-in-position":
        "external/_branches/lead-marshaller-and-wing-walkers-in-position@pre_arrival_departure",
    # event 641a25728471f56e528714e9: tdv_cone Fail = New output (default branch Pass); the deployed GS-1737 port
    "post-arrival-aircraft-walk-around-inspection-completed-accurately":
        "external/_branches/post-arrival-aircraft-walk-around-inspection-completed-accurately@tdv_cone",
    # tdv_cone Fail = New output on event 1 (with cv_common/modules overlaid from the archive @2759daf)
    "pre-departure-walk-around-completed": "external/_branches/pre-departure-walk-around-completed@tdv_cone",
    # calibration, first 5 events: green_cone_median 4/5 = New output (default 3/5); needs cv_common/modules (overlay)
    "pre-arrival-safety-huddle": "external/_branches/pre-arrival-safety-huddle@green_cone_median",
    # 5/5 ties with the default; the same pre-arrival absence logic whose branches reproduce New output elsewhere
    "fod-walk-completed": "external/_branches/fod-walk-completed@dev",
    # 5/5 ties with the default; per_component_improvement is the deployed line (handrails' reproduces New output)
    "gse-chocks": "external/_branches/gse-chocks@per_component_improvement",
    # event 641a25728471f56e528714e9: Fail = New output (default Not observed = Previous column)
    "handrails-on-gse-being-used": "external/_branches/handrails-on-gse-being-used@per_component_improvement",
    # calibration, 5 events: obstruction_hand_signals 5/5 = New output (default 3/5); imports mmpose 1.x (overlay)
    "wing-walkers-in-proper-position-and-using-approved-wands":
        "external/_branches/wing-walkers-in-proper-position-and-using-approved-wands@obstruction_hand_signals",
    # 5/5 ties with the default; the branch carries the production fix ("Fix prod error of not being able to identify
    # disconnect_frame") and its own weights (DVC)
    "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed":
        "external/_branches/conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed@new_logic",
    # steering and aircraft-chocks stay on the default branch: their newer branches tie at 5/5 and 15/15 and are feature
    # work without production fixes (steering_observability_fix 2026-08-14, towbar-attachment-fallback 2026-09-04)
}


def profile(module: str) -> dict:
    return {
        "device": DEVICE.get(module, "cuda:0"),
        "numpy1": module in NUMPY1,
        "prepend_path": PREPEND_PATH.get(module, []),
        "drop_state_keys": DROP_STATE_KEYS.get(module, ""),
        "pixel_free": module in PIXEL_FREE,
        "launcher": LAUNCHER.get(module),
        "job_class": JOB_CLASS.get(module),
        "module_dir": MODULE_DIR.get(module, ""),
    }
