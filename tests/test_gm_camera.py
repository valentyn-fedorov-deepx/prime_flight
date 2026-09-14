"""Camera-type majority vote: v1 semantics (strict majority for cone, confidence = share of the winning side)."""

from pf.gm.camera import CROP_ROWS, majority_vote
from pf.gm.context import CameraVoter


def test_no_votes_like_v1():
    assert majority_vote([]) == (None, 1.0)
    assert CameraVoter().confidence() == 1.0 and CameraVoter().majority() is None


def test_majorities_and_confidence():
    import pytest

    cone, conf = majority_vote([True, True, False])
    assert cone is True and conf == pytest.approx(2 / 3)
    cone, conf = majority_vote([False, False, True])
    assert cone is False and conf == pytest.approx(2 / 3)


def test_tie_is_wing_like_v1():
    cone, conf = majority_vote([True, False])
    assert cone is False and conf == 0.5


def test_agrees_with_context_camera_voter():
    for votes in ([True] * 7 + [False] * 3, [False] * 11 + [True] * 2, [True, False] * 5, [True]):
        voter = CameraVoter()
        for i, v in enumerate(votes):
            voter.feed(i, v)
        cone, conf = majority_vote(votes)
        assert voter.majority() == cone
        assert abs(voter.confidence() - conf) < 1e-12


def test_crop_rows_match_v1():
    assert CROP_ROWS == (150, 930)


def test_numpy_input_is_bit_identical_to_the_torchvision_transform():
    import numpy as np
    import pytest

    torch = pytest.importorskip("torch")
    transforms = pytest.importorskip("torchvision.transforms")
    Image = pytest.importorskip("PIL.Image")
    from pf.gm.camera import IMAGENET_MEAN, IMAGENET_STD, numpy_input

    trans = transforms.Compose(
        [transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)]
    )
    rng = np.random.default_rng(11)
    every_value = (np.arange(1080 * 640 * 3) % 256).astype(np.uint8).reshape(1080, 640, 3)
    frames = [rng.integers(0, 256, size=(1080, 1920, 3), dtype=np.uint8), every_value,
              np.full((1080, 640, 3), 255, np.uint8), np.zeros((1080, 640, 3), np.uint8)]
    for frame in frames:
        pil = Image.fromarray(frame[CROP_ROWS[0] : CROP_ROWS[1]]).convert("RGB")
        ref = trans(pil).unsqueeze(0)
        got = numpy_input(trans.transforms[0](pil), torch)
        assert got.dtype == ref.dtype and got.shape == ref.shape and torch.equal(got, ref)
