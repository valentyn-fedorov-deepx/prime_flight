"""Which aircraft track the causal rows carry: `longest_so_far` withholds an arriving aircraft behind an earlier, longer
track; `largest_alive` hands it over at once, keeps it against a slightly larger neighbour and counts aliased ids once."""

from types import SimpleNamespace

from pf.gm.plane_tracker import PlaneHistory
from pf.pipeline.causal_rows import CausalSecondRun
from test_gm_stream import CM  # pytest puts tests/ on sys.path

AIRPLANE = CM.id("airplane")


class FakeAircraft:
    def __init__(self):
        self.planes = {}

    def add(self, tid, frame, box):
        hist = self.planes.setdefault(tid, PlaneHistory())
        hist.frames[frame] = box
        hist.last_xyxy, hist.last_frame = box, frame

    def longest(self):
        return max(self.planes, key=lambda k: len(self.planes[k].frames)) if self.planes else None

    def snapshot(self):
        tid = self.longest()
        return {"mode_plane_height": None if tid is None else 100}


def _context(aircraft):
    return SimpleNamespace(aircraft=aircraft, layout=SimpleNamespace(snapshot=lambda: {}))


def _airplane_box(rows):
    found = [r[:4] for r in rows if int(r[-1]) == AIRPLANE]
    return [int(v) for v in found[0]] if found else None


PASSING = [1500, 400, 1900, 600]   # taxied past earlier, 300 frames
ARRIVING = [0, 300, 900, 800]      # the aircraft that parks


def _scene(rule):
    aircraft = FakeAircraft()
    causal = CausalSecondRun(_context(aircraft), CM, main_rule=rule)
    for f in range(1, 301):
        aircraft.add(1, f, PASSING)
        causal.rows(f, [])
    return aircraft, causal


def test_longest_so_far_withholds_the_arriving_aircraft():
    aircraft, causal = _scene("longest_so_far")
    for f in range(1000, 1100):
        aircraft.add(2, f, ARRIVING)
        assert _airplane_box(causal.rows(f, [])) is None  # track 1 is dead but still the longest


def test_largest_alive_hands_the_arriving_aircraft_over_at_once():
    aircraft, causal = _scene("largest_alive")
    for f in range(1000, 1100):
        aircraft.add(2, f, ARRIVING)
        assert _airplane_box(causal.rows(f, [])) == ARRIVING
    assert causal.stats.main_track_switches == 1
    assert causal._mode == 500  # the height of the held aircraft, not of the longest track


def test_largest_alive_keeps_the_held_aircraft_against_a_slightly_larger_one():
    aircraft, causal = _scene("largest_alive")
    slightly_larger = [900, 250, 1900, 800]  # 1.2 x the area of ARRIVING: under the switch factor
    much_larger = [0, 0, 1920, 1080]
    for f in range(1000, 1010):
        aircraft.add(2, f, ARRIVING)
        assert _airplane_box(causal.rows(f, [])) == ARRIVING
    for f in range(1010, 1060):  # a neighbour of similar size shows up: no flapping between the two
        aircraft.add(2, f, ARRIVING)
        aircraft.add(3, f, slightly_larger)
        assert _airplane_box(causal.rows(f, [])) == ARRIVING
    for f in range(1060, 1070):
        aircraft.add(2, f, ARRIVING)
        aircraft.add(4, f, much_larger)
        rows = causal.rows(f, [])
    assert causal._held is aircraft.planes[4] and _airplane_box(rows) == much_larger


def test_largest_alive_lets_go_of_a_track_without_boxes_and_counts_aliases_once():
    aircraft, causal = _scene("largest_alive")
    aircraft.planes[7] = aircraft.planes[1]  # norfair re-association: a second id for the same history
    assert _airplane_box(causal.rows(301, [])) is None  # no box on this frame, the track is still held
    assert causal._held is aircraft.planes[1]
    for f in range(302, 302 + 40):
        causal.rows(f, [])
    aircraft.add(2, 400, ARRIVING)
    assert _airplane_box(causal.rows(400, [])) == ARRIVING
