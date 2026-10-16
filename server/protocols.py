"""Select a scorer only from an explicit, supported manifest version."""
from . import scoring, scoring_v2


def for_manifest(manifest):
    version = manifest.get('protocol') if isinstance(manifest, dict) else None
    if version == scoring.VERSION:
        return scoring
    if version == scoring_v2.VERSION:
        return scoring_v2
    raise ValueError('Unsupported evaluation protocol.')
