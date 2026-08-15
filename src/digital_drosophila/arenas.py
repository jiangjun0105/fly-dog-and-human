"""Concentration fields and arena containers for chemotaxis benchmarks."""

from __future__ import annotations

import numpy as np


class PointSource:
    """Gaussian plume from a single point source."""

    def __init__(
        self,
        position: tuple[float, float] = (5.0, 0.0),
        sigma: float = 2.0,
        amplitude: float = 1.0,
    ):
        self._position = np.asarray(position, dtype=np.float64)
        self._sigma = sigma
        self._amplitude = amplitude

    def __call__(self, pos_xy: np.ndarray) -> float:
        r_sq = np.sum((pos_xy - self._position) ** 2)
        val = self._amplitude * np.exp(-r_sq / (2.0 * self._sigma**2))
        return float(np.clip(val, 0.0, 1.0))

    @property
    def source_position(self) -> np.ndarray:
        return self._position.copy()


class LinearGradient:
    """Uniform gradient along one axis."""

    def __init__(
        self,
        direction: tuple[float, float] = (1.0, 0.0),
        min_val: float = 0.0,
        max_val: float = 1.0,
        extent_mm: float = 10.0,
    ):
        d = np.asarray(direction, dtype=np.float64)
        self._direction = d / np.linalg.norm(d)
        self._min_val = min_val
        self._max_val = max_val
        self._extent_mm = extent_mm

    def __call__(self, pos_xy: np.ndarray) -> float:
        proj = float(np.dot(pos_xy, self._direction))
        t = proj / self._extent_mm
        t = np.clip(t, 0.0, 1.0)
        val = self._min_val + t * (self._max_val - self._min_val)
        return float(np.clip(val, 0.0, 1.0))

    @property
    def source_position(self) -> np.ndarray:
        return self._direction * self._extent_mm


class DualSource:
    """Two independent Gaussian point sources."""

    def __init__(
        self,
        pos_a: tuple[float, float] = (3.0, 3.0),
        pos_b: tuple[float, float] = (-3.0, -3.0),
        sigma_a: float = 2.0,
        sigma_b: float = 2.0,
        amplitude_a: float = 1.0,
        amplitude_b: float = 0.5,
    ):
        self._source_a = PointSource(position=pos_a, sigma=sigma_a, amplitude=amplitude_a)
        self._source_b = PointSource(position=pos_b, sigma=sigma_b, amplitude=amplitude_b)
        # Track which is stronger
        if amplitude_a >= amplitude_b:
            self._primary = self._source_a
        else:
            self._primary = self._source_b

    def __call__(self, pos_xy: np.ndarray) -> float:
        val = self._source_a(pos_xy) + self._source_b(pos_xy)
        return float(np.clip(val, 0.0, 1.0))

    @property
    def source_position(self) -> np.ndarray:
        return self._primary.source_position


class TurbulentPlume:
    """Intermittent odor plume: Gaussian backbone modulated by spatial noise."""

    def __init__(
        self,
        source_position: tuple[float, float] = (8.0, 0.0),
        wind_direction: tuple[float, float] = (-1.0, 0.0),
        plume_width: float = 2.0,
        patchiness: float = 0.5,
        seed: int = 42,
    ):
        self._source = np.asarray(source_position, dtype=np.float64)
        w = np.asarray(wind_direction, dtype=np.float64)
        self._wind = w / np.linalg.norm(w)
        self._plume_width = plume_width
        self._patchiness = patchiness
        self._seed = seed
        self._cell_size = 1.0  # mm per noise cell

    def _spatial_noise(self, pos: np.ndarray) -> float:
        cell_x = int(np.floor(pos[0] / self._cell_size))
        cell_y = int(np.floor(pos[1] / self._cell_size))
        rng = np.random.default_rng(seed=hash((self._seed, cell_x, cell_y)) % 2**32)
        return float(rng.random())

    def __call__(self, pos_xy: np.ndarray) -> float:
        # Vector from source to position
        delta = pos_xy - self._source
        # Downwind distance (projection onto wind direction)
        downwind = float(np.dot(delta, self._wind))
        if downwind < 0.0:
            # Position is upwind of source: no concentration
            return 0.0
        # Crosswind distance (perpendicular to wind)
        crosswind = float(np.abs(np.dot(delta, np.array([-self._wind[1], self._wind[0]]))))
        # Gaussian backbone: spreads with downwind distance
        spread = self._plume_width * (1.0 + 0.1 * downwind)
        backbone = np.exp(-crosswind**2 / (2.0 * spread**2))
        # Decay with downwind distance
        decay = np.exp(-downwind / 20.0)
        # Spatial noise modulation
        noise = self._spatial_noise(pos_xy)
        # Patchiness controls how much noise removes signal
        mask = 1.0 if noise > self._patchiness else 0.0
        val = backbone * decay * mask
        return float(np.clip(val, 0.0, 1.0))

    @property
    def source_position(self) -> np.ndarray:
        return self._source.copy()


class Arena:
    """Container for an environment with optional concentration field."""

    def __init__(
        self,
        name: str,
        size_mm: tuple[float, float] = (10.0, 10.0),
        concentration_field=None,
    ):
        self.name = name
        self.size_mm = size_mm
        self.field = concentration_field

    def contains(self, pos_xy: np.ndarray) -> bool:
        """Check if position is within arena bounds (centered at origin)."""
        half_x = self.size_mm[0] / 2.0
        half_y = self.size_mm[1] / 2.0
        return bool(abs(pos_xy[0]) <= half_x and abs(pos_xy[1]) <= half_y)
