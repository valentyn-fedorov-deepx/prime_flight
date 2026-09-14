# Vendored tracker dependencies

| file | source | revision | change |
|---|---|---|---|
| `tracked_object.py` | cv_common/tracked_object.py | 2759daf (tracker_optimization) | imports rewritten |
| `transport.py` | cv_common/transport.py | 2759daf | imports rewritten, `config` from `.config` |
| `track.py` | cv_common/track.py | 2759daf | none |
| `common.py` | cv_common/common.py | 2759daf | helper functions only (AST-extracted, bodies verbatim) |
| `_draw.py` | cv_common/utils/plots.py + norfair.Color | 2759daf | `plot_one_box` verbatim; `Color` stub |
| `bl_utils.py` | cv_trackers/local_utils/bl_utils.py | bd43c3c (optimization) | import rewritten |
| `config/global_config.yaml` | cv_common/global_config.yaml | 2759daf | none |
| `config/local_config.yaml` | cv_trackers/local_config.yaml | bd43c3c | none |
| `config/deep_sort.yaml` | cv_trackers/deep_sort_pytorch/configs/deep_sort.yaml | bd43c3c | none |
| `deep_sort_pytorch/` | cv_trackers/deep_sort_pytorch (runtime subset: deep_sort/, utils/parser.py) | bd43c3c | none (MIT, LICENSE kept) |

Performance patches applied on top (each one must keep the outputs identical and is listed here):

- (none yet)
