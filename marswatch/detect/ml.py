"""Method C — machine-learning change evidence (evaluated, not assumed).

We use a *pretrained* ImageNet ResNet-18 (torchvision, 11.7 M params, ~45 MB)
as a frozen feature extractor. For a candidate, the before and after chips
(radiometrically matched, identical footprint) are embedded with the layer-3
feature map; the change score is the cosine distance between the pooled
embeddings. Because absolute distances depend on terrain and illumination,
each pair is self-calibrated: the same distance is measured on random
background chips from the same registered pair, and the candidate's distance
is expressed as a robust z-score against that background.

Why not a trained Siamese / segmentation network? No public, labelled,
HiRISE-registered change-detection training set exists that we could verify;
the 19 documented HiRISE-before/after craters we found are needed for
validation and are far too few to train on. Training on them would leak the
test set. This is recorded in RESEARCH_LOG.md. The deep-feature score is
therefore treated as one more piece of evidence whose usefulness is measured
in validation, not as a validated detector.

GPU: uses Apple ``mps`` when available, else CUDA, else CPU.
"""
from __future__ import annotations

import threading

import cv2
import numpy as np

_model = None
_device = None
_lock = threading.Lock()


def available() -> bool:
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
        return True
    except ImportError:
        return False


def _load():
    global _model, _device
    with _lock:
        if _model is None:
            import torch
            import torchvision

            if torch.backends.mps.is_available():
                _device = torch.device("mps")
            elif torch.cuda.is_available():
                _device = torch.device("cuda")
            else:
                _device = torch.device("cpu")
            m = torchvision.models.resnet18(weights="IMAGENET1K_V1")
            m = torch.nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1, m.layer2, m.layer3)
            m.eval().to(_device)
            torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
            _model = m
    return _model, _device


def _chip(img: np.ndarray, rc: tuple[float, float], half: int) -> np.ndarray | None:
    r, c = int(rc[0]), int(rc[1])
    h, w = img.shape
    if r - half < 0 or c - half < 0 or r + half > h or c + half > w:
        return None
    x = img[r - half:r + half, c - half:c + half].astype(np.float32)
    x = (x - x.mean()) / (x.std() + 1e-9)
    return cv2.resize(x, (128, 128), interpolation=cv2.INTER_AREA)


def _embed(chips: list[np.ndarray]) -> np.ndarray:
    import torch

    model, dev = _load()
    x = np.stack([np.repeat(c[None], 3, 0) for c in chips]).astype(np.float32)
    with torch.no_grad():
        t = torch.from_numpy(x).to(dev)
        f = model(t)
        f = torch.nn.functional.adaptive_avg_pool2d(f, 2).flatten(1)
        f = torch.nn.functional.normalize(f, dim=1)
    return f.cpu().numpy()


def deep_distance(before: np.ndarray, after: np.ndarray, centers: list[tuple[float, float]], half: int) -> np.ndarray:
    out = np.full(len(centers), np.nan, np.float32)
    pairs = [(i, _chip(before, c, half), _chip(after, c, half)) for i, c in enumerate(centers)]
    pairs = [p for p in pairs if p[1] is not None and p[2] is not None]
    for k in range(0, len(pairs), 32):
        batch = pairs[k:k + 32]
        eb = _embed([p[1] for p in batch])
        ea = _embed([p[2] for p in batch])
        d = 1 - (eb * ea).sum(1)
        for (i, _, _), v in zip(batch, d):
            out[i] = v
    return out


def score_candidates(before_m: np.ndarray, after: np.ndarray, valid: np.ndarray, cands: list[dict],
                     res_m: float, n_background: int = 64, seed: int = 0) -> dict:
    """Add ``features.deep_dist`` and ``features.deep_z`` to each candidate. Returns calibration info."""
    if not cands or not available():
        return {"enabled": False}
    rng = np.random.default_rng(seed)
    half = 32
    h, w = valid.shape
    ys, xs = np.nonzero(valid[half:h - half:8, half:w - half:8])
    if len(ys) == 0:
        return {"enabled": False}
    idx = rng.choice(len(ys), size=min(n_background, len(ys)), replace=False)
    bg = [(half + ys[i] * 8, half + xs[i] * 8) for i in idx]
    dbg = deep_distance(before_m, after, bg, half)
    dbg = dbg[np.isfinite(dbg)]
    med = float(np.median(dbg)) if dbg.size else 0.0
    mad = float(np.median(np.abs(dbg - med)) * 1.4826 + 1e-6) if dbg.size else 1.0
    centers = []
    for c in cands:
        rc = c["features"].get("blob_rc") or c["centroid_rc"]
        centers.append((rc[0], rc[1]))
    # chip size adapted to candidate scale (at least 32 px)
    dists = deep_distance(before_m, after, centers, half)
    for c, d in zip(cands, dists):
        if np.isfinite(d):
            z = (float(d) - med) / mad
            c["features"]["deep_dist"] = round(float(d), 4)
            c["features"]["deep_z"] = round(z, 2)
            c["methods"]["C_deep_features"] = bool(z > 3.0)
            if z > 3.0:
                c["evidence_for"].append(f"pretrained CNN embedding change z={z:.1f} vs background (unvalidated evidence)")
    return {"enabled": True, "bg_median": med, "bg_mad": mad, "n_background": int(dbg.size)}
