"""Why the transport re-id costs 17.7 ms per frame, and what each change to it buys.

The belt-loader and GSE DeepSORT instances embed their crops with `torchvision.models.resnet34(pretrained=True)` — an
ImageNet classifier whose 1000 logits serve as the appearance feature (euclidean metric, MAX_DIST 150). The module is
created without `.eval()`, so BatchNorm runs in training mode (batch statistics), in fp32, one forward per tracker per
frame. This measures that forward on crops of the production size (128x64) for the batch sizes seen live, then the same
network in eval mode, with cudnn autotuning, in fp16, and with the two trackers' crops in one batch.

    python scripts/reid_bench.py [--batches 1,2,4] [--iters 200]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

import numpy as np
import torch
from torchvision import models, transforms


def bench(net, batch: int, iters: int, half: bool = False) -> dict:
    x = torch.randn(batch, 3, 128, 64, device="cuda")
    if half:
        x = x.half()
    with torch.no_grad():
        for _ in range(10):
            net(x).cpu()
        torch.cuda.synchronize()
        times = []
        for _ in range(iters):
            t0 = time.perf_counter()
            net(x).cpu().numpy()
            times.append(1000 * (time.perf_counter() - t0))
    return {"mean_ms": round(statistics.mean(times), 2), "p95_ms": round(sorted(times)[int(0.95 * len(times))], 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batches", default="1,2,4")
    ap.add_argument("--iters", type=int, default=200)
    a = ap.parse_args()
    batches = [int(x) for x in a.batches.split(",")]
    out = {"device": torch.cuda.get_device_name(0), "torch": torch.__version__, "cudnn_benchmark_default": torch.backends.cudnn.benchmark}

    net = models.resnet34(weights=models.ResNet34_Weights.IMAGENET1K_V1).cuda()  # as production: training mode
    out["train_mode_fp32"] = {b: bench(net, b, a.iters) for b in batches}
    net.eval()
    out["eval_mode_fp32"] = {b: bench(net, b, a.iters) for b in batches}
    torch.backends.cudnn.benchmark = True
    out["eval_fp32_cudnn_benchmark"] = {b: bench(net, b, a.iters) for b in batches}
    net.half()
    out["eval_fp16_cudnn_benchmark"] = {b: bench(net, b, a.iters, half=True) for b in batches}
    # the preprocessing the extractor does on the CPU: resize + ToTensor + Normalize per crop
    norm = transforms.Compose([transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    import cv2

    crops = [np.random.randint(0, 255, (300, 160, 3), dtype=np.uint8) for _ in range(4)]
    t0 = time.perf_counter()
    for _ in range(100):
        torch.cat([norm(cv2.resize(im.astype(np.float32) / 255.0, (128, 64))).unsqueeze(0) for im in crops], dim=0).float()
    out["preprocess_4_crops_ms"] = round(1000 * (time.perf_counter() - t0) / 100, 2)
    # does training-mode BN make the feature depend on the batch?
    net2 = models.resnet34(weights=models.ResNet34_Weights.IMAGENET1K_V1).cuda()
    x = torch.randn(4, 3, 128, 64, device="cuda")
    with torch.no_grad():
        alone = net2(x[:1])
        together = net2(x)[:1]
        out["train_mode_batch_dependence_max_abs_diff"] = float((alone - together).abs().max())
        net2.eval()
        alone = net2(x[:1])
        together = net2(x)[:1]
        out["eval_mode_batch_dependence_max_abs_diff"] = float((alone - together).abs().max())
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
