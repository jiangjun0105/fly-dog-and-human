"""Gait pattern analysis from leg contact data."""

from __future__ import annotations

import numpy as np


# Leg ordering: [LF, LM, LH, RF, RM, RH]
# Tripod group A: LF(0), LH(2), RM(4)
# Tripod group B: RF(3), LM(1), RH(5)
_TRIPOD_A = [0, 2, 4]
_TRIPOD_B = [3, 1, 5]


def extract_step_frequency(contact_signal: np.ndarray, dt: float) -> float:
    """Dominant stepping frequency from a single leg's contact signal via FFT.

    Searches in biologically plausible range [2, 30] Hz.
    """
    signal = contact_signal.astype(float) - contact_signal.mean()
    n = len(signal)
    if n < 2:
        return 0.0

    spectrum = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(n, d=dt)

    # Restrict to biological range
    mask = (freqs >= 2.0) & (freqs <= 30.0)
    if not mask.any():
        return 0.0

    masked_spectrum = spectrum[mask]
    masked_freqs = freqs[mask]
    return float(masked_freqs[np.argmax(masked_spectrum)])


def _autocorrelation_peak(signal: np.ndarray) -> float:
    """First non-zero-lag autocorrelation peak height, normalized to [0, 1]."""
    n = len(signal)
    if n < 3:
        return 0.0

    sig = signal - signal.mean()
    # FFT-based autocorrelation
    fft_sig = np.fft.rfft(sig, n=2 * n)
    acf = np.fft.irfft(fft_sig * np.conj(fft_sig))[:n]

    if acf[0] == 0:
        return 0.0
    acf = acf / acf[0]

    # Find first peak after zero-lag
    diff = np.diff(acf)
    peak_indices = np.where((diff[:-1] > 0) & (diff[1:] <= 0))[0] + 1

    min_lag = max(2, n // 100)
    peak_indices = peak_indices[peak_indices >= min_lag]

    if len(peak_indices) == 0:
        return 0.0

    return float(np.clip(acf[peak_indices[0]], 0.0, 1.0))


def compute_gait_regularity(leg_contacts: np.ndarray) -> float:
    """Periodicity from autocorrelation of leg contact patterns.

    Computes per-leg autocorrelation peaks and returns the mean.
    Returns 0.0 (no periodicity) to 1.0 (perfect periodicity).
    """
    contacts_f = leg_contacts.astype(float)
    n = contacts_f.shape[0]
    if n < 3:
        return 0.0

    # Average per-leg autocorrelation regularity
    peaks = [_autocorrelation_peak(contacts_f[:, i]) for i in range(6)]
    valid = [p for p in peaks if p > 0]
    if not valid:
        return 0.0
    return float(np.mean(valid))


def compute_tripod_index(leg_contacts: np.ndarray, dt: float) -> float:
    """How well the leg pattern matches a tripod gait.

    Perfect tripod: groups A and B are in anti-phase → returns 1.0.
    Uncorrelated → returns 0.0.
    """
    group_a = leg_contacts[:, _TRIPOD_A].astype(float).sum(axis=1)
    group_b = leg_contacts[:, _TRIPOD_B].astype(float).sum(axis=1)

    # Normalize to zero mean
    a = group_a - group_a.mean()
    b = group_b - group_b.mean()

    denom = np.sqrt(np.sum(a**2) * np.sum(b**2))
    if denom == 0:
        return 0.0

    # Correlation at lag 0
    correlation = np.sum(a * b) / denom

    # Perfect tripod has correlation = -1, so index = -correlation clipped to [0, 1]
    return float(np.clip(-correlation, 0.0, 1.0))


def compute_duty_factors(leg_contacts: np.ndarray) -> np.ndarray:
    """Fraction of time each leg is in stance (grounded). Returns (6,) array."""
    return np.mean(leg_contacts.astype(float), axis=0)


def classify_gait(tripod_index: float, gait_regularity: float) -> str:
    """Classify gait type based on metrics.

    Returns one of: "tripod", "tetrapod", "wave", "uncoordinated"
    """
    if gait_regularity < 0.3:
        return "uncoordinated"
    if tripod_index > 0.6 and gait_regularity > 0.5:
        return "tripod"
    if gait_regularity > 0.5 and tripod_index < 0.3:
        return "wave"
    # Intermediate coordination — tetrapod is between tripod and wave
    return "tetrapod"


def analyze_gait(leg_contacts: np.ndarray, dt: float) -> dict[str, float]:
    """Full gait analysis returning all metrics.

    Parameters
    ----------
    leg_contacts : (T, 6) boolean array
        Columns are [LF, LM, LH, RF, RM, RH]
    dt : float
        Time between samples (seconds)

    Returns
    -------
    dict with step_frequency_hz, gait_regularity, tripod_index,
    mean_duty_factor, duty_factor_symmetry, n_legs_grounded_mean
    """
    # Step frequency from summed signal across all legs
    summed_contacts = leg_contacts.any(axis=1).astype(float)
    # Use sum of all legs for better frequency estimate
    all_sum = leg_contacts.astype(float).sum(axis=1)
    step_freq = extract_step_frequency(all_sum > 0, dt)

    # Also try individual legs and take the most common dominant frequency
    leg_freqs = [extract_step_frequency(leg_contacts[:, i], dt) for i in range(6)]
    valid_freqs = [f for f in leg_freqs if f > 0]
    if valid_freqs:
        step_freq = float(np.median(valid_freqs))

    regularity = compute_gait_regularity(leg_contacts)
    tripod_idx = compute_tripod_index(leg_contacts, dt)
    duty_factors = compute_duty_factors(leg_contacts)

    # Duty factor symmetry: 1 - |mean_left - mean_right|
    left_duty = duty_factors[:3].mean()
    right_duty = duty_factors[3:].mean()
    symmetry = 1.0 - abs(left_duty - right_duty)

    n_grounded_mean = float(leg_contacts.astype(float).sum(axis=1).mean())

    return {
        "step_frequency_hz": step_freq,
        "gait_regularity": regularity,
        "tripod_index": tripod_idx,
        "mean_duty_factor": float(duty_factors.mean()),
        "duty_factor_symmetry": symmetry,
        "n_legs_grounded_mean": n_grounded_mean,
    }
