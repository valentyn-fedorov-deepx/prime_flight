"""Real-time outputs for safety-vests-secured-to-body (tdv_cone) without changing its logic.

The module decides at the end of the session. While it runs, every tracked worker carries a vest status that the module
re-evaluates on each vote once it has more than 20 votes (`Person.update_params`: UNZIPPED only when the vote sum, vest
brightness, vest size and track age allow it, ZIPPED otherwise). This hook wraps that method and emits an output whenever a
worker's status changes, right after the frame that changed it:
  * alert `vest_unzipped` — provisional: a master UNZIPPED status can revert later in the session, and the verdict can still
    come from the end-of-session v4 small-band check;
  * event `vest_zipped` — the status became zipped (including the revert of an earlier alert).
The module's `frame_id` is its 0-based enumerate index; outputs carry the branch's 1-based frame id (+1).
"""

from __future__ import annotations


def install(prod, emit) -> None:
    Person = prod.Person
    original = Person.update_params
    watched = (Person.VEST_UNZIPPED, Person.VEST_ZIPPED)

    def update_params(self, person_xyxy, vest_xyxy, vest_cls, pose_cls, img, frame_id):
        before = self._vest_status
        result = original(self, person_xyxy, vest_xyxy, vest_cls, pose_cls, img, frame_id)
        after = self._vest_status
        if after != before and after in watched:
            unzipped = after == Person.VEST_UNZIPPED
            emit("alert" if unzipped else "event", "vest_unzipped" if unzipped else "vest_zipped", frame_id + 1,
                 {"worker": self._id, "from": before, "to": after, "provisional": True})
        return result

    Person.update_params = update_params
