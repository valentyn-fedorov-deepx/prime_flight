"""Which of OUR trained models each module uses (not stock / public checkpoints), as an Excel workbook.

"Ours" is decided from the weights file itself, not from its name: Ultralytics checkpoints and ONNX exports carry the dataset
they were trained on, the class list and the date; mmengine checkpoints carry their training config; the DeepSORT re-id
head carries its number of identities. A file trained on a public dataset (COCO, Market-1501, ImageNet) or downloaded as a
release asset is stock; a file trained on our data (our class lists, our dataset names) is ours. Files whose role has no
public counterpart (zipped / unzipped vest, cone / wing camera, handrail extended) are ours by construction.

Sources: the model audits of the checkouts the monthly test set runs (docs/analysis/module_compute/*.json), the module
declarations (pf/rt/component.py) for what each module reads from the shared General Model and tracker, and the weights
files in external/ (read here when present).

    python scripts/reports/our_models_xlsx.py [docs/reports/PF_our_models_by_module.xlsx]
"""

from __future__ import annotations

import ast
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "reports", "PF_our_models_by_module.xlsx")
GM_W = os.path.join(ROOT, "external", "general_model_prod", "weights")
TRK_W = os.path.join(ROOT, "external", "cv_trackers_prod", "weights")
B = os.path.join(ROOT, "external", "_branches")


def mb(path):
    if not path or not os.path.exists(path):
        return None
    size = os.path.getsize(path) / 1e6
    return round(size, 1) if size >= 1 else round(size, 3)


def name_date(filename: str):
    """A training date written into the file name (dd_mm_yyyy), as yyyy-mm-dd."""
    import re

    m = re.search(r"(\d{2})_(\d{2})_(20\d{2})", filename)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)} (file name)" if m else ""


def onnx_meta(path):
    try:
        import onnx

        m = onnx.load(path, load_external_data=False)
        return {p.key: p.value for p in m.metadata_props}
    except Exception:
        return {}


def ul_meta(path):
    """Ultralytics .pt: dataset, date, version, class names."""
    try:
        os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
        import torch

        ck = torch.load(path, map_location="cpu", weights_only=False)
        ta = ck.get("train_args") or {}
        model = ck.get("model") or ck.get("ema")
        names = getattr(model, "names", None)
        names = list(names.values()) if isinstance(names, dict) else names
        data = (ta.get("data") or "").replace("\\", "/")
        return {"dataset": "/".join(data.split("/")[-3:-1]) if data else None, "date": (ck.get("date") or "")[:10],
                "version": ck.get("version"), "classes": names}
    except Exception:
        return {}


# ------------------------------------------------------------------------------------------------ our models
# (key, model, what it does, architecture, weights path, where it runs, status, how we know it is ours)
P = lambda *a: os.path.join(*a)  # noqa: E731
OURS = [
    ("gm_main", "General Model detector", "the main detector of the apron: aircraft and its parts, people, cones, belt loaders, GSE, pushback, doors, wheels, vests",
     "YOLOv8n-size: 3.1 M parameters (the file name says m), ONNX fp16, input 1088", P(GM_W, "GM_yolov8m_best_augmentation_march2024.onnx"), "General Model (shared)", "used, every frame",
     "trained on general_dataset.yaml, our 25 classes (ONNX metadata)"),
    ("gm_chocks", "Chocks detector v4.3", "a second detector only for chocks, at higher resolution",
     "YOLOv8s-size: 11.1 M parameters, ONNX fp16, input 1280", P(GM_W, "chocks_v4.3_200ep_yolov8.onnx"), "General Model (shared)", "used, every frame",
     "trained on chocks_dataset.yaml, class chock (ONNX metadata)"),
    ("gm_vehicle", "Vehicle detector", "vehicles and ground equipment; source of the obstacle / side-obstacle rows",
     "YOLOv8m: 25.8 M parameters, ONNX fp16, input 1088", P(GM_W, "VM_yolov8m_last_september2023.onnx"), "General Model (shared)", "used, every frame",
     "trained on our dataset.yaml, class vehicle (ONNX metadata)"),
    ("gm_camera", "Camera classifier v1.8.1", "cone or wing camera; every module switches its logic on it",
     "EfficientNet-B0 (timm), 1 output", P(GM_W, "camera_cls_effnet_b0_october_v1.8.1.pt"), "General Model (shared)",
     "used, every post-arrival frame with the main aircraft", "no public cone / wing camera classifier; versioned by us"),
    ("gm_tail", "Tail livery classifier", "the airline from the tail (report field `entity`, shown on RampVision)",
     "small CNN (TailClassifierNN)", P(GM_W, "general_tail_classifier.pth"), "General Model (shared)",
     "used, 30 calls per video (first 60 s of the main aircraft)", "our airline classes"),
    ("gm_entity_old", "Airline detector (retired)", "the previous airline detector; its calls are commented out",
     "YOLOv5 (pickled)", P(GM_W, "entity_det_aug_expnd.pt"), "General Model (shared)", "loaded, never used",
     "our airline classes; replaced by the tail classifier"),
    ("gm_old_oct", "General Model detector, October 2023", "an older version of the main detector",
     "YOLOv8m: 25.9 M parameters, ONNX", P(GM_W, "GM_yolov8m_250ep_october2023.onnx"), "General Model (shared)", "in the weights folder, not loaded",
     "trained on our dataset.yaml, same class list (ONNX metadata)"),
    ("gm_old_mar", "General Model detector, March 2024 (earlier export)", "an earlier export of the current detector's training",
     "YOLOv8n-size: 3.1 M parameters, ONNX", P(GM_W, "GM_yolov8m_best_march2024.onnx"), "General Model (shared)", "in the weights folder, not loaded",
     "trained on general_dataset.yaml (ONNX metadata)"),
    ("trk_plane", "Aircraft segmentation", "outline of each aircraft for its key points (motion state: arrival, departure)",
     "YOLO11s-seg", P(TRK_W, "yolo11s-seg_plane.pt"), "Tracker (shared)", "used, at key-point (re)initialisation",
     "trained on our plane segmentation dataset (257 videos), class plane (checkpoint metadata)"),
    ("trk_blgse", "Belt loader / GSE segmentation", "outline of belt loaders and GSE for their key points (stops, door service)",
     "YOLO26s-seg", P(TRK_W, "yolo26s_seg_bl_gse_tr10_noalb.pt"), "Tracker (shared)", "used, at key-point (re)initialisation",
     "trained on our belt loader / GSE dataset (257 videos), classes beltloader, gse (checkpoint metadata)"),
    # ---------------------------------------------------------------------------------------- module models
    ("vest_orient", "Vest orientation classifier", "which side of the worker the camera sees (back / head / side)",
     "Swin-T", P(B, "safety-vests-secured-to-body@tdv_cone", "weights", "pose_classifier.pt"), "safety vests", "used for the verdict",
     "our classes back / head / side"),
    ("vest_zip", "Vest closure classifier", "vest zipped or unzipped", "Swin-T",
     P(B, "safety-vests-secured-to-body@tdv_cone", "weights", "vest_classifier.pt"), "safety vests", "used for the verdict",
     "our classes zipped / unzipped"),
    ("vest_presence", "Vest presence gate", "is there a vest on the worker crop at all", "ResNet-18",
     P(B, "safety-vests-secured-to-body@tdv_cone", "weights", "presence_bbox_r18.pt"), "safety vests", "used for the verdict",
     "our task, trained on our crops"),
    ("vest_band", "Vest small-band classifier (v4)", "the vest band on small crops", "ResNet-18",
     P(B, "safety-vests-secured-to-body@tdv_cone", "weights", "v4_cnn2.pt"), "safety vests", "used for the verdict",
     "our task, trained on our crops"),
    ("vest_probe", "Vest CLIP probe head", "a linear head on CLIP features (auto-fail path)", "linear probe (npz)",
     P(B, "safety-vests-secured-to-body@tdv_cone", "weights", "v4_probe_head.npz"), "safety vests",
     "in the checkout, not used (switched off in v4_config.yaml)", "our head on a stock CLIP backbone"),
    ("handrail_ext", "Handrail extension classifier", "are the belt loader's handrails extended",
     "EfficientNet-B0 (torchvision)",
     P(ROOT, "external", "safety-handrails-fully-extended", "weights", "efficientNetb0_300_epoch_general_classifier_dataset_safety_handrails_v3_26_09_2023.pth"),
     "handrails on GSE; handrails fully extended", "used for the verdict (same file in both modules)",
     "our classes extended / not extended, dataset v3, 26.09.2023"),
    ("handrail_seg", "Handrail segmentation", "where the handrails are, for the contact check", "Unet with MiT-B0 encoder",
     P(B, "handrails-on-gse-being-used@per_component_improvement", "weights", "safety_handrails_mit_b0_best_model_293_epoch_30_10_2023.pth"),
     "handrails on GSE", "used for the verdict", "our one-class handrail mask, 30.10.2023"),
    ("hand_contact", "Hand-contact classifier", "is the worker's hand on the handrail", "EfficientNet-B0 (timm)",
     P(B, "handrails-on-gse-being-used@per_component_improvement", "weights", "effnetb0_weighted_norm_aug_929.pt"),
     "handrails on GSE", "used for the verdict", "our task, trained on our hand crops"),
    ("gse_chock_diff", "GSE chock classifier (frame difference)", "is a chock placed at a stopped GSE wheel", "EfficientNet-B0 (timm)",
     P(B, "gse-chocks@per_component_improvement", "weights", "effnetb0_small_clean_64_960.pt"), "GSE parked and chocked",
     "used for the verdict", "our task, trained on our wheel strips"),
    ("ac_chock_diff", "Aircraft chock classifier (frame difference)", "is a chock at the rear wheel (main gear)", "EfficientNet-B0 (timm)",
     P(ROOT, "external", "aircraft-chocks", "weights", "effnetb0_ext_fix_993.pt"), "aircraft chocks (3 verdicts)",
     "used for the verdict", "our task, trained on our wheel crops"),
    ("ac_hose", "Conditioned-air hose detector", "the air-conditioning hose and whether it is still connected",
     "YOLO11s-seg", P(B, "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed@new_logic", "weights", "yolo11s_seg-det_ac_tr18_noalb.pt"),
     "conditioned air removed", "used for the verdict", "trained on our AC-hose dataset, class hose (checkpoint metadata)"),
    ("ac_unit_old", "Air-conditioning unit detector (previous)", "the earlier detector of the AC unit", "YOLOv8, ONNX",
     P(B, "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed@new_logic", "weights", "best28_full.onnx"),
     "conditioned air removed", "in the checkout, never loaded", "trained on our ac_dataset.yaml, class air_conditioning (ONNX metadata)"),
    ("pin_tsai", "Pin-installation classifier", "is the steering bypass pin being installed, from the worker's pose over time",
     "InceptionTime (tsai), with a fitted MinMaxScaler (scaler.gz)",
     P(ROOT, "external", "steering-by-pass-pin-installed-or-steering-otherwise-bypassed", "weights", "model_newaug.pkl"),
     "steering bypass pin", "used for the verdict", "our task, trained on our pose sequences"),
    ("lm_role", "Worker role classifier", "who is the lead marshaller / a wing walker", "SVC (scikit-learn)",
     P(B, "lead-marshaller-and-wing-walkers-in-position@pre_arrival_departure", "models", "worker_classifier_svc.pkl"),
     "lead marshaller and wing walkers", "used for the verdict", "our features and labels"),
    ("lm_walk", "Walk-along classifier", "does the worker walk along with the aircraft", "RandomForest (scikit-learn)",
     P(B, "lead-marshaller-and-wing-walkers-in-position@pre_arrival_departure", "models", "walk_along_classifier_rfc.pkl"),
     "lead marshaller and wing walkers", "used for the verdict", "our features and labels"),
    ("lm_start", "Walk-start models (left, right)", "when the wing walkers start moving", "gradient boosting (scikit-learn), two files",
     P(B, "lead-marshaller-and-wing-walkers-in-position@pre_arrival_departure", "models", "right_walk_start_prediction_sgb.pkl"),
     "lead marshaller and wing walkers", "used for the verdict", "our features and labels"),
    ("lm_type_old", "Worker type classifiers (two)", "an earlier role model", "DecisionTree / kNN pipelines (scikit-learn)",
     P(B, "lead-marshaller-and-wing-walkers-in-position@pre_arrival_departure", "models", "worker_type_classifier.pkl"),
     "lead marshaller and wing walkers", "in the checkout, not loaded", "our features and labels"),
    ("wand", "Wand detector", "the approved wands in the wing walkers' hands", "YOLOv5",
     P(B, "wing-walkers-in-proper-position-and-using-approved-wands@obstruction_hand_signals", "wand_detector.pt"),
     "wing walkers with wands", "not used: load commented out on the branch the test set runs; on the default branch loaded and never run",
     "trained by us, class wand, 30.05.2022 (checkpoint metadata)"),
    ("hair", "Hair classifier", "hair tied / covered as the policy requires (night model)", "EfficientNet-B0 (torchvision)",
     P(ROOT, "external", "hair-policy", "weights", "night_efficientNetb0_223_epoch_06_01_2024.pth"), "hair policy",
     "used (Pyarmor build: calls unreadable)", "our task, 06.01.2024"),
    ("inside_out", "Inside / outside classifier", "is the worker inside or outside the scene of interest", "EfficientNet-B0 (torchvision)",
     P(ROOT, "external", "hair-policy", "weights", "inside_outside_efficientnet_b0_best_model_17_epoch.pt"), "hair policy",
     "used (Pyarmor build: calls unreadable)", "our task"),
    ("wa_post", "Walk-around coverage CNN (post-arrival)", "was the aircraft walked around: a classifier on the walk-around canvas",
     "small CNN (torch)", P(B, "post-arrival-aircraft-walk-around-inspection-completed-accurately@tdv_cone", "weights", "best_model.pth"),
     "post-arrival walk-around", "used for the verdict", "our task, trained on our walk-around canvases"),
    ("wa_pre", "Walk-around coverage CNN (pre-departure)", "the same for the pre-departure walk-around", "small CNN (Keras, run through a torch twin)",
     P(B, "pre-departure-walk-around-completed@tdv_cone", "weights", "best_acc.keras"), "pre-departure walk-around",
     "used for the verdict", "our task, trained on our walk-around canvases"),
]

STOCK = [
    ("MobileSAM vit_t", "mobile_sam.pt", "official MobileSAM release", "General Model (main-aircraft mask); safety zone clear; both walk-arounds"),
    ("DeepSORT re-id network", "scripted_ckpt.t7", "deep_sort_pytorch checkpoint: classifier head of 751 identities = Market-1501", "Tracker (people)"),
    ("ResNet-34", "torchvision resnet34(pretrained=True)", "ImageNet weights downloaded by torchvision", "Tracker (belt loader and GSE re-id)"),
    ("CRAFT text detector + EasyOCR", "craft / easyocr packages", "public packages and their release weights", "General Model (airline from the fuselage text)"),
    ("HRNet-W48 COCO 256x192", "td-hm_hrnet-w48_8xb32-210e_coco-256x192-0e67c616_20220913.pth", "official mmpose COCO checkpoint (hash in the name matches the file)", "hand signals; steering bypass pin; lead marshaller and wing walkers; wing walkers with wands"),
    ("HRNet-W48 COCO 384x288 dark", "hrnet_w48_coco_384x288_dark-741844ba_20200812.pth", "official mmpose checkpoint; present, loaded by nobody", "hand signals; steering; lead marshaller; wing walkers (checkouts)"),
    ("SimCC ResNet-50 COCO 384x288", "simcc_res50_8xb32-140e_coco-384x288-45c3ba34_20220913.pth", "official OpenMMLab COCO training (its config: openmmlab COCO data root, person_keypoints_train2017)", "pushback pin verification"),
    ("RTMPose-l", "rtmpose-l-4dba18fc.onnx", "official RTMPose release", "GSE parked and chocked"),
    ("DWPose-l whole body", "dw-ll_ucoco_384.onnx", "official DWPose release", "handrails on GSE"),
    ("MoveNet SinglePose Thunder v4", "movenet_singlepose_thunder_4.onnx", "official TF Hub release", "FOD walk"),
    ("YOLOv8m-pose", "yolov8m-pose.pt", "official Ultralytics asset: coco-pose.yaml, 2023-04-19, 8.0.77 (checkpoint metadata)", "safety vests; both walk-arounds"),
    ("Depth Anything V2 metric ViT-B", "depth_anything_v2_metric_vkitti_vitb.pth", "official release", "both walk-arounds"),
    ("CLIP ViT-H-14 backbone", "open_clip", "public weights (only the probe head on top is ours, and it is switched off)", "safety vests"),
    ("MediaPipe", "mediapipe package", "public package", "hair policy"),
]

# module -> (readable name, repository), in checklist order
MODULES = [
    ("chocks-and-cones-available-and-staged-for-arrival", "chocks and cones staged"),
    ("crew-present-10-minutes-prior-to-aircraft-arrival", "crew present"),
    ("fod-walk-completed", "FOD walk"),
    ("pre-arrival-safety-huddle", "safety huddle"),
    ("safety-vests-secured-to-body", "safety vests"),
    ("safety-zone-confirmed-clear", "safety zone clear"),
    ("hair-policy", "hair policy"),
    ("aircraft-chocks", "aircraft chocks (3 verdicts)"),
    ("cones-placed-in-proper-positions-and-timely", "cones placed"),
    ("steering-by-pass-pin-installed-or-steering-otherwise-bypassed", "steering bypass pin"),
    ("lead-marshaller-and-wing-walkers-in-position", "lead marshaller and wing walkers"),
    ("bl_rear_cone", "belt loader rear cone"),
    ("hand-signals", "hand signals"),
    ("post-arrival-aircraft-walk-around-inspection-completed-accurately", "post-arrival walk-around"),
    ("3-stop-brake-check", "3-stop brake check"),
    ("all-cargo-bin-doors-opened-and-verified", "cargo doors opened"),
    ("gse-chocks", "GSE parked and chocked"),
    ("handrails-on-gse-being-used", "handrails on GSE"),
    ("safety-handrails-fully-extended", "handrails fully extended"),
    ("conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed", "conditioned air removed"),
    ("cones-are-removed-only-after-all-gse-is-clear-of-aircraft-and-chocked", "cones removed after GSE clear"),
    ("beltloader-chocks", "belt loader forward chock"),
    ("pin-verification", "pushback pin verification"),
    ("pre-departure-walk-around-completed", "pre-departure walk-around"),
    ("pushback-does-not-start-until-wing-walkers-are-in-place-and-ready", "pushback waits for wing walkers"),
    ("pushback-pathway-confirmed-clear-of-obstacles", "pushback pathway clear"),
    ("wing-walkers-in-proper-position-and-using-approved-wands", "wing walkers with wands"),
]
OWN = {  # module -> keys of OURS that run inside the module
    "safety-vests-secured-to-body": ["vest_orient", "vest_zip", "vest_presence", "vest_band"],
    "handrails-on-gse-being-used": ["handrail_ext", "handrail_seg", "hand_contact"],
    "safety-handrails-fully-extended": ["handrail_ext"],
    "gse-chocks": ["gse_chock_diff"],
    "aircraft-chocks": ["ac_chock_diff"],
    "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed": ["ac_hose"],
    "steering-by-pass-pin-installed-or-steering-otherwise-bypassed": ["pin_tsai"],
    "lead-marshaller-and-wing-walkers-in-position": ["lm_role", "lm_walk", "lm_start"],
    "hair-policy": ["hair", "inside_out"],
    "post-arrival-aircraft-walk-around-inspection-completed-accurately": ["wa_post"],
    "pre-departure-walk-around-completed": ["wa_pre"],
}
UNUSED = {
    "safety-vests-secured-to-body": ["vest_probe"],
    "conditioned-air-removed-10-mins-prior-to-departure-and-properly-stowed": ["ac_unit_old"],
    "lead-marshaller-and-wing-walkers-in-position": ["lm_type_old"],
    "wing-walkers-in-proper-position-and-using-approved-wands": ["wand"],
}
STOCK_IN = {
    "safety-vests-secured-to-body": "YOLOv8m-pose",
    "safety-zone-confirmed-clear": "MobileSAM",
    "fod-walk-completed": "MoveNet Thunder",
    "hand-signals": "HRNet-W48 COCO",
    "steering-by-pass-pin-installed-or-steering-otherwise-bypassed": "HRNet-W48 COCO",
    "lead-marshaller-and-wing-walkers-in-position": "HRNet-W48 COCO",
    "wing-walkers-in-proper-position-and-using-approved-wands": "HRNet-W48 COCO",
    "pin-verification": "SimCC ResNet-50 COCO",
    "gse-chocks": "RTMPose-l",
    "handrails-on-gse-being-used": "DWPose-l",
    "hair-policy": "MediaPipe",
    "post-arrival-aircraft-walk-around-inspection-completed-accurately": "YOLOv8m-pose, Depth Anything V2, MobileSAM",
    "pre-departure-walk-around-completed": "YOLOv8m-pose, Depth Anything V2, MobileSAM",
}


def shared_for(module: str) -> list:
    """Our shared models a module reads, from its declared inputs (the GM classes and tracked classes it consumes)."""
    from pf.rt.component import ComponentSpec

    try:
        spec = ComponentSpec.for_module(module)
    except Exception:
        return []
    gm = set(spec.gm_classes or ())
    trk = set(spec.tracker_classes or ())
    out = []
    if gm - {"chock", "vehicle", "obstacle", "side_obstacle"} or trk:
        out.append("General Model detector")
    if "chock" in gm:
        out.append("Chocks detector v4.3")
    if gm & {"vehicle", "obstacle", "side_obstacle"}:
        out.append("Vehicle detector")
    if "airplane" in trk:
        out.append("Aircraft segmentation")
    if trk & {"beltloader", "gse"}:
        out.append("Belt loader / GSE segmentation")
    return out


def main() -> int:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    cons = json.load(io.open(os.path.join(ROOT, "docs", "analysis", "module_consumption.json"), encoding="utf-8"))["modules"]
    by_key = {o[0]: o for o in OURS}
    details = {}
    for key, name, role, arch, path, where, status, why in OURS:
        meta = {}
        if path.endswith(".onnx"):
            md = onnx_meta(path)
            if md:
                try:
                    classes = list(ast.literal_eval(md.get("names", "{}")).values())
                except Exception:
                    classes = []
                desc = md.get("description", "")
                meta = {"dataset": desc.split("trained on ")[-1] if "trained on" in desc else None,
                        "date": (md.get("date") or "")[:10], "version": md.get("version"), "classes": classes}
        elif path.endswith(".pt") and os.path.basename(path).startswith(("yolo", "wand")):
            meta = ul_meta(path)
        if key == "wand" and not meta:  # YOLOv5: its classes and date were read with a lenient unpickler (no YOLOv5 code here)
            meta = {"classes": ["wand"], "date": "2022-05-30"}
        details[key] = meta

    used_by = {k: [] for k in by_key}
    used_by["gm_camera"] = ["every module: its cone / wing decision selects the module's camera logic"]
    used_by["gm_tail"] = ["no check: the report field `entity` (airline) for RampVision"]
    for mod, short in MODULES:
        if mod == "hair-policy":
            for k in OWN.get(mod, []):
                used_by[k].append(short)
            continue
        for k in OWN.get(mod, []) + UNUSED.get(mod, []):
            used_by[k].append(short)
        for s in shared_for(mod):
            for k, o in by_key.items():
                if o[1] == s:
                    used_by[k].append(short)

    wb = Workbook()
    font = Font(name="Arial", size=10)
    bold = Font(name="Arial", size=10, bold=True)
    head_fill = PatternFill("solid", fgColor="DCE3EC")
    shared_fill = PatternFill("solid", fgColor="F3F5F8")
    thin = Side(style="thin", color="C9CDD3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical="top")

    def sheet(ws, headers, rows, widths, fills=None):
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill, c.border, c.alignment = bold, head_fill, border, wrap
        for i, r in enumerate(rows):
            ws.append(["—" if v in (None, "", []) else v for v in r])
            for c in ws[ws.max_row]:
                c.font, c.border, c.alignment = font, border, wrap
                if fills and fills[i]:
                    c.fill = fills[i]
        for i, w in enumerate(widths):
            ws.column_dimensions[chr(65 + i)].width = w
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions

    # ---------------------------------------------------------------- sheet 1: by module
    ws = wb.active
    ws.title = "Modules - our models"
    rows, fills = [], []
    rows.append(["General Model (shared)", "detectors/general_model @ a0157a4 (production)", "every check, through its detections and report",
                 "General Model detector; Chocks detector v4.3; Vehicle detector; Camera classifier v1.8.1; Tail livery classifier",
                 "—", "Airline detector (retired, loaded, never used); two older General Model exports (not loaded)",
                 "MobileSAM; CRAFT + EasyOCR"])
    fills.append(shared_fill)
    rows.append(["Tracker (shared)", "utils/cv_trackers @ bd43c3c (production)", "every check that reads tracks",
                 "Aircraft segmentation; Belt loader / GSE segmentation", "General Model detector (its detections)", "—",
                 "DeepSORT re-id (Market-1501); ResNet-34 (ImageNet)"])
    fills.append(shared_fill)
    for mod, short in MODULES:
        own = [by_key[k][1] for k in OWN.get(mod, [])]
        unused = [f"{by_key[k][1]} ({by_key[k][6]})" for k in UNUSED.get(mod, [])]
        shared = shared_for(mod)
        tasks = "; ".join(cons.get(mod, {}).get("checks") or []) or ("Hair Policy" if mod == "hair-policy" else "")
        if mod == "hair-policy":
            shared = ["not readable (Pyarmor build)"]
        rows.append([short, mod, tasks, "; ".join(own) if own else "none of its own",
                     "; ".join(shared) + ("; Camera classifier v1.8.1 (cone / wing)" if shared and mod != "hair-policy" else ""),
                     "; ".join(unused), STOCK_IN.get(mod, "")])
        fills.append(None)
    sheet(ws, ["Module", "Repository (dxgat/detectors/...)", "Checklist task(s)", "Our models inside the module (used)",
               "Our shared models it depends on (General Model / tracker)", "Ours, but not used", "Stock models it also runs (not counted)"],
          rows, [28, 40, 44, 52, 52, 46, 36], fills)

    # ---------------------------------------------------------------- sheet 2: catalogue
    ws2 = wb.create_sheet("Our models - catalogue")
    rows2, fills2 = [], []
    for key, name, role, arch, path, where, status, why in OURS:
        meta = details.get(key) or {}
        classes = meta.get("classes")
        classes = ", ".join(map(str, classes)) if classes else ""
        rows2.append([name, role, arch, classes, meta.get("dataset") or "", meta.get("date") or name_date(os.path.basename(path)),
                      os.path.basename(path), mb(path), where, "; ".join(dict.fromkeys(used_by.get(key, []))) or "—",
                      status, why])
        fills2.append(shared_fill if where.endswith("(shared)") else None)
    sheet(ws2, ["Model", "What it does", "Architecture", "Classes / output (from the file)", "Trained on (from the file)",
                "Training / export date (from the file)", "Weights file", "Size, MB", "Where it runs", "Modules that use it",
                "Status", "Why it counts as ours"], rows2, [30, 44, 26, 40, 30, 16, 46, 9, 22, 46, 30, 44], fills2)

    # ---------------------------------------------------------------- sheet 3: stock, excluded
    ws3 = wb.create_sheet("Stock models - excluded")
    sheet(ws3, ["Model", "File / package", "Why it is stock", "Where it runs"], [list(s) for s in STOCK], [30, 52, 60, 52])

    # ---------------------------------------------------------------- sheet 4: notes
    ws4 = wb.create_sheet("Notes")
    notes = [
        ["Prepared", "2026-10-09, Valentyn Fedorov"],
        ["Scope", "The 27 module repositories behind the client's 30 checks (seat-belts is out of scope), the production "
                  "General Model (a0157a4) and tracker (bd43c3c). Module models are taken from the checkouts the monthly "
                  "test set runs (some are branches, named in docs/analysis/module_compute)."],
        ["Ours vs stock", "Decided from the weights files: Ultralytics checkpoints and ONNX exports carry their training "
                          "dataset, class list and date; mmengine checkpoints carry their training config; the DeepSORT "
                          "re-id head has 751 outputs (Market-1501). Trained on our data (our class lists, our dataset "
                          "names) = ours; trained on COCO / Market-1501 / ImageNet or a release asset = stock. Models whose "
                          "task has no public counterpart (vest zipped, cone / wing camera, handrail extended) are ours."],
        ["Shared models per module", "From the module's declared inputs (pf/rt/component.py): the General Model classes and "
                                     "tracked classes it reads. Every module also depends on the camera classifier, whose "
                                     "cone / wing decision selects the module's camera logic."],
        ["Fitted preprocessing", "steering: scaler.gz (MinMaxScaler fitted with the pin classifier) is listed with it, not "
                                 "as a separate model."],
        ["Not verifiable", "hair policy is a Pyarmor build: its two classifiers are named in its config; how they are "
                           "called cannot be read."],
        ["Sources", "docs/analysis/module_compute/pose_person.json, scene_gse.json; docs/analysis/module_consumption.json; "
                    "the weights files under external/; scripts/reports/our_models_xlsx.py builds this file."],
    ]
    sheet(ws4, ["Item", "Note"], notes, [24, 120])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    n_used = sum(1 for o in OURS if o[6].startswith("used"))
    print(f"written {OUT}: {len(OURS)} of our models ({n_used} used), {len(STOCK)} stock, {len(MODULES)} modules")
    missing = [os.path.relpath(o[4], ROOT) for o in OURS if not os.path.exists(o[4])]
    print("weights files not found locally:", missing or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
