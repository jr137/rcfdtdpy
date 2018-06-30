import numpy as np

"""Contains the classes used to represent a simulation"""

class Sim:
    """Represents a single simulation."""
    
    def __init__(self, vacuum_permittivity, infinity_permittivity, delta_t, delta_z, num_n, num_i, current, susceptibility):
        self._vacuum_permittivity = vacuum_permittivity
        self._infinity_permittivity = infinity_permittivity
        self._delta_t = delta_t
        self._delta_z = delta_z
        self._current = current
        self._susceptibility = susceptibility

    def set_vacuum_permittivity(self, vacuum_permittivity):
        """
        Sets :math:`\epsilon_0`

        :param vacuum_permittivity: :math:`\epsilon_0`
        """
        self._vacuum_permittivity = vacuum_permittivity

    def get_vacuum_permittivity(self):
        """
        Gets :math:`\epsilon_0`
        
        :returns: :math:`\epsilon_0`
        """
        return self._vacuum_permittivity

    def set_infinity_permittivity(self, infinity_permittivity):
        """
        Sets :math:`\epsilon_\infty`

        :param infinity_permittivity: :math:`\epsilon_\infty`
        """
        self._infinity_permittivity = infinity_permittivity

    def get_delta_t(self):
        """
        Gets :math:`\Delta t`
        
        :returns: :math:`\Delta t`
        """
        return self._delta_t

    def set_delta_t(self, delta_t):
        """
        Sets :math:`\Delta t`
        
        :param delta_t: :math:`\Delta t`
        """
        self._delta_t = delta_t

    def get_delta_z(self):
        """
        Gets :math:`\Delta z`
        
        :returns: :math:`\Delta z`
        """
        return self._delta_z

    def set_delta_z(self, delta_z):
        """
        Sets :math:`\Delta z`
        
        :param delta_z: :math:`\Delta z`
        """
        self._delta_z = delta_z

    def _calc_electric_susceptibility(self):
        pass

    def _calc_efield_susceptibility_convolution(self):
        pass

    def _iterate_efield(self):
        pass

    def _iterate_mfield(self):
        pass

class Current:
    """Represents a current"""

    def __init__(self):
        pass

class Field:
    """Represents either an electric or magnetic field"""

    def __init__(self, num_i):
        self._field = list(np.zeros(num_i, dtype=np.complex64))

    def get_field(self, n=0):
        return self._field[n]

    def iterate_field(self, next_state):
        self._field.append(next_state)