"""Configuration of the vendored tracker: cv_common global_config.yaml @2759daf updated by the production tracker's
local_config.yaml @bd43c3c — the same merge as `cv_common.common.parse_config` (top-level keys of the local file
replace the global ones), loaded from the vendored copies instead of the current working directory.
"""

import os

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))


def load_config() -> dict:
    with open(os.path.join(_HERE, 'config', 'global_config.yaml'), encoding='utf-8') as fh:
        cfg = yaml.load(fh, Loader=yaml.FullLoader)
    with open(os.path.join(_HERE, 'config', 'local_config.yaml'), encoding='utf-8') as fh:
        cfg.update(yaml.load(fh, Loader=yaml.FullLoader))
    return cfg


def deep_sort_config():
    from .deep_sort_pytorch.utils.parser import get_config

    cfg = get_config()
    cfg.merge_from_file(os.path.join(_HERE, 'config', 'deep_sort.yaml'))
    return cfg


config = load_config()
