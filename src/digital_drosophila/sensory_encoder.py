"""Sensory encoder: convert FlyGym body state to input currents for ascending neurons.

Maps proprioceptive signals (joint angles, velocities) and body velocity
to current injections for the 15 ascending neurons in the 100-neuron sample.

Usage:
    encoder = SensoryEncoder(ascending_indices, n_actuated=66)
    currents = encoder.encode(joint_angles, body_vel)
"""

import numpy as np


class SensoryEncoder:
    """Encode body state as input currents for ascending neurons.

    Parameters
    ----------
    ascending_indices : list of int
        Indices of ascending neurons in the Brian2 NeuronGroup.
    n_neurons : int
        Total number of neurons in the network.
    n_actuated : int
        Number of actuated DOFs (joint angles to read).
    gain_pa : float
        Maximum current in pA (will be converted to Amperes for Brian2).
    vel_gain_pa : float
        Maximum current from body velocity in pA.
    """

    def __init__(self, ascending_indices, n_neurons=100, n_actuated=66,
                 gain_pa=500.0, vel_gain_pa=300.0):
        self.ascending_indices = list(ascending_indices)
        self.n_ascending = len(self.ascending_indices)
        self.n_neurons = n_neurons
        self.n_actuated = n_actuated
        self.gain = gain_pa * 1e-12  # Convert pA to Amperes
        self.vel_gain = vel_gain_pa * 1e-12

        # Assign joints to ascending neurons (round-robin by leg)
        # 6 legs x 11 DOFs = 66 actuated joints
        # 15 ascending neurons: 12 get proprioceptive input (2 per leg),
        # 3 get body velocity input
        self.n_proprio = min(12, self.n_ascending)
        self.n_vel = self.n_ascending - self.n_proprio

        # Build assignment: each proprioceptive neuron gets a slice of joints
        self.joint_assignments = []
        joints_per_neuron = n_actuated // self.n_proprio
        for i in range(self.n_proprio):
            start = i * joints_per_neuron
            end = start + joints_per_neuron if i < self.n_proprio - 1 else n_actuated
            self.joint_assignments.append((start, end))

    def encode(self, joint_angles, body_vel):
        """Convert body state to current array for injection into the network.

        Parameters
        ----------
        joint_angles : ndarray
            Joint angle values (n_actuated,). Radians, centred around neutral.
        body_vel : ndarray
            Body linear velocity (3,) in mm/s.

        Returns
        -------
        currents : ndarray
            Current values for all neurons (n_neurons,) in Amperes.
            Only ascending neuron entries are non-zero.
        """
        currents = np.zeros(self.n_neurons)

        # Proprioceptive channels: mean absolute deviation of assigned joints
        for i in range(self.n_proprio):
            start, end = self.joint_assignments[i]
            # Use absolute joint angle as a proxy for proprioceptive signal
            # Normalize by pi (max possible angle) and scale by gain
            signal = np.mean(np.abs(joint_angles[start:end])) / np.pi
            signal = np.clip(signal, 0.0, 1.0)
            asc_idx = self.ascending_indices[i]
            currents[asc_idx] = signal * self.gain

        # Velocity channels: body velocity components
        for i in range(self.n_vel):
            vel_idx = i % 3  # cycle through x, y, z
            # Normalize velocity (typical fly speed: 0-30 mm/s)
            signal = np.abs(body_vel[vel_idx]) / 30.0
            signal = np.clip(signal, 0.0, 1.0)
            asc_idx = self.ascending_indices[self.n_proprio + i]
            currents[asc_idx] = signal * self.vel_gain

        return currents
