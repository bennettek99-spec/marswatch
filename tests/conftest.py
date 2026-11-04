from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def hirise_crop() -> np.ndarray:
    """512x512 crop of real HiRISE PSP_007168_1980 (NASA/JPL/UArizona), scaled to 0..1 float32."""
    im = cv2.imread(str(FIX / "hirise_PSP_007168_1980_crop.png"), cv2.IMREAD_UNCHANGED)
    return (im.astype(np.float32) / 65535.0) * 0.1 + 0.15  # roughly I/F-like range


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    from marswatch import db as dbmod

    d = dbmod.Database(tmp_path / "t.db")
    monkeypatch.setattr(dbmod, "_db", d)
    return d


def shift_image(img: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Content of ``img`` at p appears at p + (dx, dy) in the output."""
    h, w = img.shape
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
