# Vendored tracker dependencies

| file | source | revision | change |
|---|---|---|---|
| `tracked_object.py` | cv_common/tracked_object.py | 2759daf (tracker_optimization) | imports rewritten |
| `transport.py` | cv_common/transport.py | 2759daf | imports rewritten, `config` from `.config` |
| `track.py` | cv_common/track.py | 2759daf | none |
| `common.py` | cv_common/common.py | 2759daf | helper functions + their dependency closure (AST-extracted, bodies verbatim) |
| `_draw.py` | cv_common/utils/plots.py + norfair.Color | 2759daf | `plot_one_box` + imports verbatim (`import random` added: not bound in the source module); `Color` constants |
| `bl_utils.py` | cv_trackers/local_utils/bl_utils.py | bd43c3c (optimization) | import rewritten |
| `config/global_config.yaml` | cv_common/global_config.yaml | 2759daf | none |
| `config/local_config.yaml` | cv_trackers/local_config.yaml | bd43c3c | none |
| `config/deep_sort.yaml` | cv_trackers/deep_sort_pytorch/configs/deep_sort.yaml | bd43c3c | none |
| `deep_sort_pytorch/` | cv_trackers/deep_sort_pytorch (runtime subset: deep_sort/, utils/parser.py) | bd43c3c | none (MIT, LICENSE kept) |

Nothing in this directory is hand-edited. Performance changes are separate modules (`pf/tracker/fast_*.py`) enabled
through `TrackerOptions`, each proven output-identical with seeded runs against the production pin.
