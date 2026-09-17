import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pf.rt.component import ComponentSpec, Gate, OutputBus  # noqa: E402
from pf.rt.runtime import Output  # noqa: E402
from test_rt_module_host import fake_module  # noqa: E402

CLASS_IDS = {"gse": 5, "pushback": 6, "trailer": 7, "obstacle": 8, "beltloader": 2, "person": 1, "airplane": 0}


def test_a_module_declares_what_it_reads_and_when_it_is_open():
    spec = ComponentSpec.for_module("3-stop-brake-check")
    assert spec.declared and spec.pixels is False
    assert set(spec.tracker_classes) == {"airplane", "beltloader"}
    assert "pushback" in spec.gm_classes and "gse" in spec.gm_classes
    # gate proposal: it counts the belt loader's stops, so it opens at arrival, not at its own decision
    assert (spec.open_on, spec.close_on) == ("T_ARR", "BL_LEAVE")
    assert "module" in spec.as_dict() and spec.as_dict()["gate"]["open_on"] == "T_ARR"


def test_an_undeclared_module_is_given_everything():
    spec = ComponentSpec.for_module("a-module-nobody-analysed")
    assert not spec.declared
    meta = {"general_model": [[0, 0, 1, 1, 0.9, 5]], "trackers": [{"cls_str": "person"}]}
    assert spec.subscription(CLASS_IDS.get).filter(meta) == meta


def test_a_component_is_given_only_the_rows_it_declared():
    spec = ComponentSpec.for_module("3-stop-brake-check")
    sub = spec.subscription(CLASS_IDS.get)
    meta = {"general_model": [[0, 0, 1, 1, 0.9, CLASS_IDS["pushback"]], [0, 0, 1, 1, 0.9, CLASS_IDS["person"]],
                              [0, 0, 1, 1, 0.9, CLASS_IDS["gse"]]],
            "trackers": [{"cls_str": "airplane"}, {"cls_str": "person"}, {"cls_str": "beltloader"}]}
    kept = sub.filter(meta)
    assert [int(r[5]) for r in kept["general_model"]] == [CLASS_IDS["pushback"], CLASS_IDS["gse"]]
    assert [r["cls_str"] for r in kept["trackers"]] == ["airplane", "beltloader"]
    assert meta["general_model"][1][5] == CLASS_IDS["person"]  # the record itself is not mutated


def test_the_trackers_own_optical_flow_state_is_not_sent_to_a_module_that_never_reads_it():
    spec = ComponentSpec.for_module("3-stop-brake-check")
    assert "_status" in " ".join(spec.private_fields) and not spec.reads_optical_flow_state()  # _status is not _st
    record = {"tr_id": 1, "cls_str": "beltloader", "xyxy": [0, 0, 1, 1],
              "state_dict": {"_status": "stopped", "_obj_id": 1, "_p0": [[1, 2]] * 200, "_st": [1] * 200}}
    kept = spec.subscription(CLASS_IDS.get).filter({"general_model": [], "trackers": [record]})["trackers"][0]
    assert kept["state_dict"]["_status"] == "stopped" and kept["state_dict"]["_obj_id"] == 1
    # emptied, not removed: the module hands the state back to cv_common's from_state_dict, which looks every key up
    assert kept["state_dict"]["_p0"] == [] and kept["state_dict"]["_st"] == []
    assert len(record["state_dict"]["_p0"]) == 200  # the branch keeps its own copy whole


def test_a_gate_opens_and_closes_on_stage_events():
    spec = ComponentSpec.for_module("pushback-pathway-confirmed-clear-of-obstacles")
    gate = Gate(spec, enabled=True)
    assert not gate.open and gate.on_events(10, ["T_ARR"]) is None
    assert gate.on_events(100, ["BL_LEAVE"]) == "open" and gate.open and gate.opened_at == 100
    assert gate.on_events(200, []) is None and gate.open
    assert gate.on_events(300, ["T_DEP_PLUS_60"]) == "close" and gate.closed and gate.closed_at == 300
    assert gate.on_events(400, ["BL_LEAVE"]) is None  # a closed component does not reopen


def test_an_undeclared_gate_is_open_from_the_first_frame():
    gate = Gate(ComponentSpec.for_module("a-module-nobody-analysed"), enabled=True)
    assert gate.open and gate.opened_at == 1 and gate.on_events(5, ["T_ARR"]) is None


def test_the_bus_delivers_to_its_sinks_and_keeps_the_production_moment():
    seen = []
    bus = OutputBus(sinks=[seen.append], capture_time=lambda fid: 100.0)
    out = Output("verdict", "m", 7, {"status": "Fail"})
    bus.publish(out, received_t=100.4)
    assert out.emitted_t == 100.4 and seen[0]["latency_s"] == 0.4 and seen[0]["kind"] == "verdict"
    assert bus.drain() == [out] and bus.drain() == []
    assert bus.report()["by_kind"] == {"verdict": 1}


def test_a_broken_sink_is_dropped_not_raised():
    def bad(record):
        raise RuntimeError("no endpoint")

    bus = OutputBus(sinks=[bad])
    bus.publish(Output("alert", "a", 1, {}))
    assert bus.sinks == [] and bus.report()["sink_errors"][0]["error"].startswith("RuntimeError")
    bus.publish(Output("alert", "a", 2, {}))  # the branch keeps running without it
    assert len(bus.records) == 2


def test_a_verdict_reaches_the_bus_without_waiting_for_the_next_frame(tmp_path):
    """The module decides at frame 20; the parent must have it before anything else is pushed."""
    from pf.rt.module_host import ModuleHost

    bus = OutputBus()
    host = ModuleHost("fake_early", {"module_dir": fake_module(tmp_path, "fake_early", stop_at=20), "device": "cpu",
                                     "work_dir": str(tmp_path / "work")}, bus=bus)
    host.start({"video": "src.mp4", "n_frames": 48}, 8.0)
    try:
        for fid in range(1, 21):
            assert host.push(fid, {"general_model": [], "trackers": []}) == []  # a bus takes the outputs instead
        outs = bus.wait(timeout_s=30.0)
        assert [o.name for o in outs] == ["fake_early"]
        assert outs[0].payload["status"] == "Fail" and outs[0].payload["decided_after_frame"] == 20
        assert outs[0].emitted_t and outs[0].emitted_t <= time.perf_counter()
    finally:
        host.close()


def test_a_closed_gate_holds_the_frames_back_and_the_report_says_so(tmp_path):
    from pf.rt.module_host import ModuleHost

    spec = ComponentSpec("fake_gated", pixels=False, open_on="T_ARR", close_on="T_DEP", declared=False)
    bus = OutputBus()
    host = ModuleHost("fake_gated", {"module_dir": fake_module(tmp_path, "fake_gated"), "device": "cpu",
                                     "work_dir": str(tmp_path / "work_gated")}, spec=spec, bus=bus, gating=True)
    host.start({"video": "src.mp4", "n_frames": 48}, 8.0)
    try:
        for fid in range(1, 11):
            host.push(fid, {"general_model": [[0, 0, 1, 1, 0.9, 5]], "trackers": []})
        host.push(11, {"general_model": [[0, 0, 1, 1, 0.9, 5]], "trackers": []}, events=["T_ARR"])
        for fid in range(12, 21):
            host.push(fid, {"general_model": [[0, 0, 1, 1, 0.9, 5]], "trackers": []})
        host.push(21, {"general_model": [], "trackers": []}, events=["T_DEP"])
        for fid in range(22, 25):
            host.push(fid, {"general_model": [], "trackers": []})
        outs = host.close()
    finally:
        pass
    verdict = next(o for o in [*outs, *bus.drain()] if o.kind == "verdict")
    # the module was given frames 11..20 (the close event fires before frame 21 is sent) and counted them as its own 1..10
    assert verdict.payload["report"] == ["fake_gated: 10 frames, 10 rows"]
    # reported in absolute ids (X2): it asked for frame 21, which its closed gate never delivered, and then returned
    assert verdict.frame_id == 21 and verdict.payload["frames_delivered"] == 10
    report = host.report()
    assert report["frames_sent"] == 10 and report["frames_skipped_gate_closed"] == 14
    assert report["gate"]["opened_at"] == 11 and report["gate"]["closed_at"] == 21
    assert [r["name"] for r in bus.records if r["kind"] == "event"] == ["component_open", "component_close"]


def test_without_a_stage_detector_a_gated_component_still_gets_every_frame():
    """The first gated run starved its modules: the table named events nothing publishes yet."""
    spec = ComponentSpec.for_module("pushback-pathway-confirmed-clear-of-obstacles")
    assert spec.open_on == "BL_LEAVE"
    gate = Gate(spec)  # gating off: no event source
    assert gate.open and gate.opened_at == 1
    assert gate.on_events(100, ["BL_LEAVE"]) is None and gate.open  # the table is reported, not applied
    assert "no stage events yet" in gate.as_dict()["gating"]
