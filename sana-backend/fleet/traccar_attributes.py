"""
Central metadata for Traccar position attributes used by SANA.

This module contains presentation metadata only. It must never store position
values or act as a second source of GPS telemetry; Traccar remains authoritative.

Unknown attributes must remain visible in reports using their original key.
"""

from typing import Any


# Metadata for known Traccar attributes.
#
# Keys must match the attribute names returned by the Traccar API.
# Add entries only after confirming the attribute name, meaning, and unit
# against Traccar documentation or the relevant device decoder.
#
# Supported optional fields:
#   label:      Persian display name
#   unit:       Display unit (only when its meaning is confirmed)
#   category:   Group used in the position-details UI
#   value_type: Optional presentation hint (e.g. "boolean", "number", "text")
#
# Do not add per-position values here.
TRACCAR_ATTRIBUTES: dict[str, dict[str, Any]] = {}


def get_attribute_metadata(attribute_key: str) -> dict[str, Any]:
    """
    Return presentation metadata for a known attribute.

    For an unknown attribute, preserve its original key as the display label.
    This ensures newly received decoder attributes are not hidden just because
    they have not yet been documented in this registry.
    """
    metadata = TRACCAR_ATTRIBUTES.get(attribute_key)

    if metadata is not None:
        return {
            **metadata,
            "key": attribute_key,
            "label": metadata.get("label") or attribute_key,
            "known": True,
        }

    return {
        "key": attribute_key,
        "label": attribute_key,
        "known": False,
    }
