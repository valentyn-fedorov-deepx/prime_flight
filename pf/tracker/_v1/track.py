"""VENDORED verbatim from cv_common/track.py @2759daf.""" 
from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class Track:
    """Class to save Tracker results in convenient format"""
    tr_id: Optional[int] = 0
    xyxy: Optional[Union[list, tuple]] = (0, 0, 0, 0)
    cls_str: Optional[str] = 'Object'
    conf: Optional[float] = 0.0

    state_dict: Optional[dict] = field(default_factory=dict)
    data: Optional[dict] = None

    def to_json(self) -> dict:
        return self.__dict__

    def from_json(self, state_dict):
        self.__dict__.update(state_dict)
        return self


if __name__ == '__main__':  # small test
    t1 = Track()
    print(t1)
    print(Track(1, (0, 1, 0, 1), 'Obj', 0.4))
    t2 = Track().from_json(t1.to_json())
    print(t2)
