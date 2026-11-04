"""Central configuration for MARSWATCH.

All values may be overridden with environment variables prefixed ``MARSWATCH_``
(e.g. ``MARSWATCH_DATA_DIR=/Volumes/ext/marswatch``). Defaults are chosen for a
small Apple Silicon Mac mini: bounded cache, few worker threads, tile-wise
processing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(f"MARSWATCH_{name}", default)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(REPO_ROOT / "data"))))
    # Archive endpoints (real, verified 2026-11-04; see RESEARCH_LOG.md)
    pds_base: str = _env("PDS_BASE", "https://hirise-pds.lpl.arizona.edu/PDS")
    stac_api: str = _env("STAC_API", "https://stac.astrogeology.usgs.gov/api")
    stac_collection: str = _env("STAC_COLLECTION", "mro_hirise_uncontrolled_observations")
    cog_base: str = _env(
        "COG_BASE", "https://astrogeo-ard.s3-us-west-2.amazonaws.com/mars/mro/hirise/uncontrolled"
    )
    uahirise_base: str = _env("UAHIRISE_BASE", "https://www.uahirise.org")
    # Resource budgets
    cache_budget_mb: int = int(_env("CACHE_BUDGET_MB", "2048"))
    max_workers: int = int(_env("MAX_WORKERS", "2"))
    gdal_cache_mb: int = int(_env("GDAL_CACHE_MB", "256"))
    memory_limit_mb: int = int(_env("MEMORY_LIMIT_MB", "4096"))
    requests_per_second: float = float(_env("REQUESTS_PER_SECOND", "4"))
    # Processing defaults
    work_resolution_m: float = float(_env("WORK_RES_M", "1.0"))
    tile_px: int = int(_env("TILE_PX", "1024"))
    max_pair_area_km2: float = float(_env("MAX_PAIR_AREA_KM2", "40"))

    @property
    def db_path(self) -> Path:
        return Path(_env("DB_PATH", str(self.data_dir / "marswatch.db")))

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def reference_dir(self) -> Path:
        return self.data_dir / "reference"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.cache_dir, self.runs_dir, self.index_dir, self.reference_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
