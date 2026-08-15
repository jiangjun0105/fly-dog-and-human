"""Olfactory encoder: convert chemical concentration fields to input currents.

Models bilateral antennae that sample a concentration field and produce
current injections via Weber-Fechner encoding. Pure numpy — no Brian2 or
FlyGym dependency.

Usage:
    encoder = OlfactoryEncoder()
    result = encoder.encode(concentration_field, fly_pos_xy, heading_rad)
"""

import numpy as np


class OlfactoryEncoder:
    """Encode odor concentration as bilateral antenna currents.

    Parameters
    ----------
    n_channels : int
        Number of independent odor channels.
    antenna_separation_mm : float
        Distance between left and right antenna in mm.
    rate_max_hz : float
        Maximum ORN firing rate.
    half_saturation : float
        Weber-Fechner half-saturation constant (K).
    current_scale_pa : float
        Maximum output current in pA (stored internally as Amperes).
    """

    def __init__(self, n_channels: int = 1, antenna_separation_mm: float = 0.2,
                 rate_max_hz: float = 200.0, half_saturation: float = 0.1,
                 current_scale_pa: float = 500e-12):
        self.n_channels = n_channels
        self.antenna_separation_mm = antenna_separation_mm
        self.rate_max_hz = rate_max_hz
        self.half_saturation = half_saturation
        self.current_scale_pa = current_scale_pa

        # Precompute normalization denominator: log(1 + C_max/K) with C_max=1
        self._log_norm = np.log(1.0 + 1.0 / self.half_saturation)

    def get_antenna_positions(self, fly_pos_xy: np.ndarray,
                              heading_rad: float) -> tuple[np.ndarray, np.ndarray]:
        """Compute world positions of left and right antennae.

        Left antenna is 90 deg CCW from heading, right is 90 deg CW.

        Returns
        -------
        (left_pos_xy, right_pos_xy) : tuple of ndarray, each shape (2,)
        """
        half_sep = self.antenna_separation_mm / 2.0
        # Perpendicular direction (CCW from heading = left)
        perp_x = -np.sin(heading_rad)
        perp_y = np.cos(heading_rad)

        offset = half_sep * np.array([perp_x, perp_y])
        left_pos = fly_pos_xy + offset
        right_pos = fly_pos_xy - offset
        return left_pos, right_pos

    def _weber_fechner(self, concentration: float) -> float:
        """Apply Weber-Fechner law to map concentration to normalized rate."""
        c = np.clip(concentration, 0.0, 1.0)
        return np.log(1.0 + c / self.half_saturation) / self._log_norm

    def encode(self, concentration_field, fly_pos_xy: np.ndarray,
               heading_rad: float) -> dict:
        """Convert odor concentration at antennae to neural input currents.

        Parameters
        ----------
        concentration_field : callable
            f(pos_xy) -> float, concentration in [0, 1].
        fly_pos_xy : array-like, shape (2,)
            Fly's current XY position in mm.
        heading_rad : float
            Heading angle in radians (0 = positive X).

        Returns
        -------
        dict with keys:
            left_current_pa, right_current_pa : float (Amperes)
            concentration_left, concentration_right : float
            bilateral_difference : float — (left - right) normalized by sum
        """
        fly_pos_xy = np.asarray(fly_pos_xy, dtype=float)
        left_pos, right_pos = self.get_antenna_positions(fly_pos_xy, heading_rad)

        conc_left = float(concentration_field(left_pos))
        conc_right = float(concentration_field(right_pos))

        rate_left = self._weber_fechner(conc_left)
        rate_right = self._weber_fechner(conc_right)

        current_left = rate_left * self.current_scale_pa
        current_right = rate_right * self.current_scale_pa

        # Bilateral difference normalized by sum (avoids division by zero)
        total = rate_left + rate_right
        if total > 0:
            bilateral_diff = (rate_left - rate_right) / total
        else:
            bilateral_diff = 0.0

        return {
            "left_current_pa": current_left,
            "right_current_pa": current_right,
            "concentration_left": conc_left,
            "concentration_right": conc_right,
            "bilateral_difference": bilateral_diff,
        }
