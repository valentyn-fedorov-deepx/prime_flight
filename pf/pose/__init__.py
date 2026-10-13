"""Shared person pose for the pose modules (PF-Q4-02 pose unification).

Five production modules run their own torch pose network through mmpose 1.x (HRNet-W48 in hand-signals, steering,
lead-marshaller, wing-walkers; SimCC ResNet-50 in pin-verification) and one already runs RTMPose-l on ONNX Runtime
(gse-chocks); fod-walk runs MoveNet Thunder. `topdown_onnx` is one mmpose-faithful top-down runner for SimCC ONNX
exports (RTMPose, DWPose); `shims` serves the modules' own pose interfaces from it without changing module code.
"""
