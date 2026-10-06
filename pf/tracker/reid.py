"""Cost switches for the transport re-id of the vendored DeepSORT (belt loaders and GSE).

Production embeds every transport crop with `torchvision.models.resnet34(pretrained=True)` created without `.eval()`: an
ImageNet classifier in training mode, fp32, one forward per tracker per frame — the single most expensive step of the
tracker (15–18 ms per frame on a busy stretch, `docs/analysis/rt_optimisation_plan.md`). The vendored class is left as it
is (`pf.tracker._v1` is the production pin); these switches reconfigure an instance after it is built:

  * `eval_mode`  BatchNorm on its running statistics instead of the batch's — the feature of a crop no longer depends on
                 which other crops share the batch. NOT exact against production: gated by module verdicts.
  * `half`       fp16 weights and activations behind a wrapper that keeps the extractor's float32 interface. NEAR.

`torch.backends.cudnn.benchmark` is a process-wide switch and is set by the caller.
"""

from __future__ import annotations

import torch
from torch import nn


class _HalfForward(nn.Module):
    """Runs the wrapped module in fp16 and hands back float32, so the caller's preprocessing and `.numpy()` stay as they are."""

    def __init__(self, module: nn.Module):
        super().__init__()
        self.module = module.half()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.module(x.half()).float()


def configure_resnet_extractor(extractor, eval_mode: bool = False, half: bool = False) -> dict:
    """Apply the switches to one `ResNetExtractor` instance in place; returns what was changed."""
    net = extractor.net
    changed = {}
    if eval_mode and net.training:
        net.eval()
        changed["eval_mode"] = True
    if half and not isinstance(net, _HalfForward):
        if extractor.device != "cuda":
            raise ValueError("fp16 re-id needs the cuda device")
        extractor.net = _HalfForward(net)
        changed["half"] = True
    return changed
