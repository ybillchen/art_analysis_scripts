"""
BSD 3-Clause License
Copyright (c) 2025 Yingtian Chen
All rights reserved.

Galaxy naming convention: maps simulation folder paths to single-letter labels.
"""

GALAXIES = [
    ("mh2e12_km/1113433", "a"),
    ("mh2e12_km/1113673", "b"),
    ("mh2e12_km/1113831", "c"),
    ("mh2e12_km/1117028", "d"),
    ("mh2e12_km/1117038", "e"),
    ("mh3e12_km/1116392", "f"),
    ("mh3e12_km/1117206", "g"),
    ("mh3e12_km/1118550", "h"),
    ("mh5e12_km/1112809", "i"),
    ("mh5e12_km/1116287", "j"),
]

GALAXY_LABELS = {path: label for path, label in GALAXIES}
GALAXY_PATHS  = {label: path for path, label in GALAXIES}
GALAXY_LIST   = [path for path, _ in GALAXIES]


def get_label(basepath):
    """Get the letter label for a basepath (e.g. '.../mh2e12_km/1113433/run' → 'a')."""
    parts = basepath.rstrip('/').replace('\\', '/').split('/')
    for n in (2, 3):
        if len(parts) >= n:
            key = '/'.join(parts[-n:])
            if key in GALAXY_LABELS:
                return GALAXY_LABELS[key]
            if key.endswith('/run'):
                key = key[:-4]
                if key in GALAXY_LABELS:
                    return GALAXY_LABELS[key]
    return None


def resolve_galaxy(name):
    """Resolve a galaxy argument: accept a letter label or a folder path.
    Returns the folder path (e.g. 'f' → 'mh3e12_km/1116392')."""
    if name in GALAXY_PATHS:
        return GALAXY_PATHS[name]
    return name
