"""GM second pass: the on-demand preprocessing must equal ImagePreprocessor.get_preprocessed() in every mode, and the
working frame must use the mode of its own frame."""

import numpy as np
import pytest

pytest.importorskip("cv2")

from pf.gm.preprocessor import ImagePreprocessor, Mode  # noqa: E402
from pf.gm.second_pass import _WorkingFrame, preprocess_frame  # noqa: E402


class _Owner:
    preprocessed_frames = 0


@pytest.mark.parametrize("mode", list(Mode))
def test_preprocess_frame_equals_get_preprocessed(mode):
    rng = np.random.default_rng(3)
    frame = rng.integers(0, 256, size=(40, 64, 3), dtype=np.uint8)
    pre = ImagePreprocessor(noise_fn=lambda f: 0.0)
    pre.update(1, frame)
    pre.mode = mode
    ref = pre.get_preprocessed()
    got = preprocess_frame(frame, mode)
    assert got.dtype == ref.dtype and np.array_equal(got, ref)


def test_working_frame_is_lazy_and_keeps_its_mode():
    rng = np.random.default_rng(4)
    frame = rng.integers(0, 256, size=(32, 48, 3), dtype=np.uint8)
    owner = _Owner()
    w = _WorkingFrame(frame, True, Mode.MIDDLE, owner)
    assert owner.preprocessed_frames == 0
    img = w.get()
    assert owner.preprocessed_frames == 1 and np.array_equal(img, preprocess_frame(frame, Mode.MIDDLE))
    assert w.get() is img and owner.preprocessed_frames == 1
    raw = _WorkingFrame(frame, False, Mode.HEAVY, owner)
    assert raw.get() is frame and owner.preprocessed_frames == 1
