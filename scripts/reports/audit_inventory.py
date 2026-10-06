"""Assemble the audit inventory: every module, what it checks, what it reads, which models it runs (file, size, hash,
framework), which revisions it is pinned to, in which stage window it is active, how long it runs (post job, batch per
recorded frame, live per frame), whether it runs in real time as it is, and the review's attention note.

Sources (all generated or measured earlier; nothing is run here):
  docs/analysis/module_consumption.json      what each module reads from GM / tracker, passes, pins, entry point
  docs/analysis/module_dataset_needs.json    own models (short), class groups, stage recomputation
  docs/analysis/module_compute/*.json        the model audits of the pixel modules (file, size, sha256, architecture)
  docs/analysis/rt_module_cost.json          post-job seconds, live ms per frame, real-time readiness, verdict timing
  docs/streaming_ref/module_map.json         stage window, decision type
  docs/04_modules.md                         tier / cameras / ProdReady, reviewed pin
  docs/arch_review/essential_inventory.json  the review's attention note per task
  tasks/notes/PF-Q2-11.md                    batch ms per recorded frame (contended machine)

    python scripts/reports/audit_inventory.py   -> docs/reports/audit_inventory.json
"""

from __future__ import annotations

import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "reports", "audit_inventory.json")


def load(rel: str):
    return json.load(io.open(os.path.join(ROOT, rel), encoding="utf-8"))


def read(rel: str) -> str:
    return io.open(os.path.join(ROOT, rel), encoding="utf-8").read()


def main() -> int:
    cons = load("docs/analysis/module_consumption.json")["modules"]
    needs = {r["module"]: r for r in load("docs/analysis/module_dataset_needs.json")["modules"]}
    cost = {r["module"]: r for r in load("docs/analysis/rt_module_cost.json")["modules"]}
    mmap = {r["name"]: r for r in load("docs/streaming_ref/module_map.json")["modules"]}
    review = {v["id"]: v for v in load("docs/arch_review/essential_inventory.json")["review_views"]}
    compute = {}
    for rel in ("docs/analysis/module_compute/pose_person.json", "docs/analysis/module_compute/scene_gse.json"):
        j = load(rel)
        mods = j["modules"]
        for m in (mods if isinstance(mods, list) else mods.values()):
            compute[m["module"]] = m

    # 04_modules.md: tier / cameras / ProdReady and the reviewed pin, by M-id
    md = read("docs/04_modules.md")
    tier, pins = {}, {}
    for block in re.split(r"\n### ", md)[1:]:
        head = block.split("\n", 1)[0]
        mid = head.split(" · ")[0].strip()
        t = re.search(r"\*\*Tier / cameras / ProdReady\*\*: (\S+) · ([^·\n]+) · ProdReady=(\w+)", block)
        p = re.search(r"pinned `([0-9a-f]+)`", block)
        if t:
            tier[mid] = {"tier": t.group(1), "cameras": t.group(2).strip(), "prod_ready": t.group(3)}
        if p:
            pins[mid] = p.group(1)

    # PF-Q2-11: batch ms per recorded frame
    batch = {}
    note = read("tasks/notes/PF-Q2-11.md")
    for line in note.splitlines():
        if line.startswith("| ") and "·" in line and "ms per recorded" not in line:
            for item in re.findall(r"([a-z0-9\-]+) ([0-9]+\.[0-9]+)", line):
                batch.setdefault(item[0], float(item[1]))

    def mid_of(name: str) -> str:
        return cons.get(name, {}).get("m_id") or ""

    def tier_of(mid: str) -> dict:
        for key in (mid, mid + "A"):
            if key in tier:
                return tier[key]
        return {}

    def attention_of(mid: str) -> str:
        notes = [review[k]["attention"] for k in sorted(review) if k == mid or (k.startswith(mid) and len(k) == len(mid) + 1)]
        return " ".join(n.strip() for n in notes if n)

    def models_of(name: str) -> list:
        out = []
        comp = compute.get(name)
        if comp:
            for mdl in comp.get("models") or []:
                size = mdl.get("size_bytes")
                if isinstance(size, list):
                    size = sum(x for x in size if isinstance(x, (int, float)))
                text = lambda v: v if isinstance(v, str) or v is None else json.dumps(v, ensure_ascii=False)  # noqa: E731
                files = mdl.get("weights_path") or mdl.get("weights_file") or ""
                if isinstance(files, list):
                    files = ", ".join(os.path.basename(str(f)) for f in files)
                else:
                    files = os.path.basename(str(files))
                out.append({
                    "name": text(mdl.get("name")),
                    "architecture": text(mdl.get("architecture")),
                    "file": files,
                    "size_mb": round(size / 1e6, 1) if isinstance(size, (int, float)) and size else None,
                    "sha256_16": text(mdl.get("sha256_16")),
                    "framework": text(mdl.get("framework")),
                    "cadence": text(mdl.get("calls_per_frame") or mdl.get("cadence") or mdl.get("called_at")),
                })
        else:
            for short in (needs.get(name, {}).get("own_models") or []):
                out.append({"name": short, "architecture": None, "file": None, "size_mb": None, "sha256_16": None,
                            "framework": None, "cadence": None})
        return out

    batch_key = {  # module -> PF-Q2-11 short label
        "safety-vests-secured-to-body": "safety-vests", "safety-zone-confirmed-clear": "safety-zone",
        "lead-marshaller-and-wing-walkers-in-position": "lead-marshaller", "fod-walk-completed": "fod-walk",
        "pre-arrival-safety-huddle": "huddle", "chocks-and-cones-available-and-staged-for-arrival": "chocks-and-cones",
        "crew-present-10-minutes-prior-to-aircraft-arrival": "crew-present", "hand-signals": "hand-signals",
        "aircraft-chocks": "aircraft-chocks", "cones-placed-in-proper-positions-and-timely": "cones-placed",
        "steering-by-pass-pin-installed-or-steering-otherwise-bypassed": "steering",
        "handrails-on-gse-being-used": "handrails-on-gse", "safety-handrails-fully-extended": "safety-handrails",
        "gse-chocks": "gse-chocks", "3-stop-brake-check": "3-stop", "beltloader-chocks": "beltloader-chocks",
        "bl_rear_cone": "bl_rear_cone", "all-cargo-bin-doors-opened-and-verified": "all-cargo",
        "cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked": "cones-removed",
        "pin-verification": "pin-verification",
        "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed": "conditioned-air",
        "pushback-pathway-confirmed-clear-of-obstacles": "pushback-pathway",
        "wing-walkers-in-proper-position-and-using-approved-wands": "wing-walkers",
        "pushback-does-not-start-until-wing-walkers-are-in-place-and-ready": "pushback-does-not-start",
        "post-arrival-aircraft-walk-around-inspection-completed-accurately": "post-arrival",
        "pre-departure-walk-around-completed": "pre-departure",
    }
    walk = {"post-arrival": 6.8, "pre-departure": 26.1}

    rows = []
    for name, c in cons.items():
        mid = (c.get("m_id") or "").split("/")[0]
        if not mid:
            continue  # seat belts: out of scope
        nd, co, mp = needs.get(name, {}), cost.get(name, {}), mmap.get(name, {})
        cfg = c.get("config") or {}
        ev = [x for x in (c["tracker"].get("events_recomputed_locally") or []) if x and not x.lower().startswith("none")]
        bk = batch_key.get(name)
        rows.append({
            "m_id": mid, "module": name, "checks": c.get("checks"),
            "tier": tier_of(mid).get("tier"), "cameras": tier_of(mid).get("cameras"), "prod_ready": tier_of(mid).get("prod_ready"),
            "reviewed_pin": pins.get(mid) or pins.get(mid + "A"), "repo_head": cfg.get("repo_head"),
            "cv_common_pin": cfg.get("cv_common_pin"), "db_worker_pin": cfg.get("db_worker_pin"),
            "entry": (c.get("entry") or "").split(" ")[0],
            "stage": mp.get("stage"), "opens": mp.get("opens"), "closes": mp.get("closes"), "decision": mp.get("decision"),
            "preventive": mp.get("preventive"), "streaming_verdict": mp.get("verdict"),
            "passes": c.get("passes"), "pixels": bool(c["pixels"].get("reads_frames")),
            "gm_classes": c["gm"].get("class_names") or [], "gm_cosmetic": c["gm"].get("class_names_cosmetic") or [],
            "reads_conf": c["gm"].get("conf_used"),
            "tracker_classes": c["tracker"].get("classes") or [], "private_fields": c["tracker"].get("private_fields") or [],
            "events_recomputed": ev, "recomputes_stage": nd.get("recomputes_the_stage_itself"),
            "models": models_of(name),
            "post_job_s": co.get("post_job_s"), "live_ms_per_frame": (co.get("whole_event_ms") or {}).get("module"),
            "batch_ms_per_recorded_frame": batch.get(bk) if bk else None,
            "runs_in_real_time_as_is": co.get("runs_in_real_time_as_is"), "verdict_arrives": co.get("verdict_arrives"),
            "attention": attention_of(mid),
            "chunkwise_blockers": c.get("chunkwise_blockers") or [],
        })
        if bk in walk:
            rows[-1]["batch_ms_per_recorded_frame"] = walk[bk]
    rows.sort(key=lambda r: r["m_id"])

    def size_of(path: str):
        p = os.path.join(ROOT, path)
        return round(os.path.getsize(p) / 1e6, 1) if os.path.exists(p) else None

    gm_dir, trk_dir = "external/general_model_prod/weights", "external/cv_trackers_prod/weights"
    shared = {
        "general_model": [
            {"name": "GM YOLOv8m (apron classes)", "file": "GM_yolov8m_best_augmentation_march2024.onnx", "input": "1088x1088 fp16",
             "cadence": "every frame", "ms_busy": 8.5, "ms_pure": 4.27, "size_mb": size_of(f"{gm_dir}/GM_yolov8m_best_augmentation_march2024.onnx")},
            {"name": "Chocks YOLOv8 v4.3", "file": "chocks_v4.3_200ep_yolov8.onnx", "input": "1280x1280 fp16", "cadence": "every frame",
             "ms_busy": 3.0, "ms_pure": 5.59, "size_mb": size_of(f"{gm_dir}/chocks_v4.3_200ep_yolov8.onnx")},
            {"name": "Vehicle YOLOv8m", "file": "VM_yolov8m_last_september2023.onnx", "input": "1088x1088 fp16", "cadence": "every frame",
             "ms_busy": 5.8, "ms_pure": 8.31, "size_mb": size_of(f"{gm_dir}/VM_yolov8m_last_september2023.onnx")},
            {"name": "MobileSAM vit_t (main-aircraft mask)", "file": "mobile_sam.pt", "input": "1024 (full frame)", "cadence": "every frame with the main aircraft",
             "ms_busy": None, "ms_pure": None, "size_mb": size_of(f"{gm_dir}/mobile_sam.pt")},
            {"name": "Entity (airline) YOLOv5", "file": "entity_det_aug_expnd.pt", "input": "1280", "cadence": "every 8th frame, up to 40 hits",
             "ms_busy": None, "ms_pure": None, "size_mb": size_of(f"{gm_dir}/entity_det_aug_expnd.pt")},
            {"name": "Camera cone/wing EfficientNet-B0 v1.8.1", "file": "camera_cls_effnet_b0_october_v1.8.1.pt", "input": "224 (rows 150:930)",
             "cadence": "every post-arrival frame with the main aircraft, CPU", "ms_busy": None, "ms_pure": None,
             "size_mb": size_of(f"{gm_dir}/camera_cls_effnet_b0_october_v1.8.1.pt")},
            {"name": "Tail classifier", "file": "general_tail_classifier.pth", "input": "crop", "cadence": "aircraft type vote",
             "ms_busy": None, "ms_pure": None, "size_mb": size_of(f"{gm_dir}/general_tail_classifier.pth")},
        ],
        "tracker": [
            {"name": "DeepSORT re-id, workers (TorchScript)", "file": "scripted_ckpt.t7", "input": "64x128 crops", "cadence": "every frame with persons",
             "ms_busy": 4.1, "size_mb": size_of(f"{trk_dir}/scripted_ckpt.t7")},
            {"name": "DeepSORT re-id, belt loaders and GSE (torchvision ResNet-34, ImageNet, training mode)", "file": "torchvision resnet34",
             "input": "128x64 crops", "cadence": "every frame with BL / GSE, two instances", "ms_busy": 15.2, "size_mb": 87.3},
            {"name": "Plane segmentor YOLO11s-seg", "file": "yolo11s-seg_plane.pt", "input": "640", "cadence": "at keypoint (re)initialisation, every 8 frames per object",
             "ms_busy": None, "size_mb": size_of(f"{trk_dir}/yolo11s-seg_plane.pt")},
            {"name": "BL / GSE segmentor YOLO26s-seg", "file": "yolo26s_seg_bl_gse_tr10_noalb.pt", "input": "640", "cadence": "the same, cached per class per frame",
             "ms_busy": 4.2, "size_mb": size_of(f"{trk_dir}/yolo26s_seg_bl_gse_tr10_noalb.pt")},
            {"name": "FAST keypoints + PyrLK optical flow (OpenCV, CPU)", "file": "—", "input": "<=250 points per object", "cadence": "every frame",
             "ms_busy": 12.0, "size_mb": None},
            {"name": "estimate_sigma noise estimate (scikit-image, CPU)", "file": "—", "input": "full frame", "cadence": "every 2 s",
             "ms_busy": 2.1, "size_mb": None},
        ],
    }
    json.dump({"generated": "2026-10-06", "modules": rows, "shared": shared},
              io.open(OUT, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
    print(f"{len(rows)} modules -> {os.path.relpath(OUT, ROOT)}")
    for r in rows:
        print(f"{r['m_id']:5s} {r['module'][:38]:38s} models={len(r['models'])} post={r['post_job_s']} batch={r['batch_ms_per_recorded_frame']} "
              f"live={r['live_ms_per_frame']} pin={r['reviewed_pin']} head={r['repo_head']} cvc={r['cv_common_pin']} stage={r['stage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
