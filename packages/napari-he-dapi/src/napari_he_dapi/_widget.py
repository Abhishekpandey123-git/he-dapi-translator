"""napari plugin widget: H&E <-> DAPI virtual staining."""
from __future__ import annotations

import numpy as np
from magicgui import magicgui
from napari.types import ImageData


@magicgui(
    call_button="Run virtual staining",
    direction={"choices": ["he2dapi", "dapi2he"], "label": "Direction"},
)
def translate(image: ImageData, direction: str = "he2dapi") -> ImageData:
    """Translate the active image with the he-dapi model.

    Returns a new layer with the predicted (virtual) stain.
    """
    from he_dapi import translate as _translate

    arr = np.asarray(image)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return _translate(arr, direction=direction)
