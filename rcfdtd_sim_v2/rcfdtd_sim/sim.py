from abc import ABC, abstractmethod
import numpy as np
from tqdm import tqdm

"""
Contains the classes used to represent a simulation
"""


class Simulation:
    r"""Represents a single simulation. Field is initialized to all zeros.

    :param i0: The spatial value at which the field starts
    :param i1: The spatial value at which the field ends
    :param di: The spatial step size
    :param n0: The temporal value at which the field starts
    :param n1: The temporal value at which the field ends
    :param dn: The temporal step size
    :param epsilon0: :math:`\epsilon_0`, the vacuum permittivity
    :param mu0: :math:`\mu_0`, the vacuum permeability
    :param boundary: The boundary type of the field, either 'zero', for fields bounded by zeros or 'absorbing' for
    absorbing boundary conditions
    :param currents: A Current object or a tuple of Current objects that represent the currents present in the
    simulation, defaults to none
    :param materials: A Material object or a tuple of Material objects that represent the materials present in the
    simulation, defaults to none
    :param nstore: A tuple of time indices to save field values at in all points in space
    :param istore: A tuple of spatial indices to save field values at in all points in time
    """

    def __init__(self, i0, i1, di, n0, n1, dn, epsilon0, mu0, boundary, currents=(), materials=(), nstore=(),
                 istore=()):
        # -------------
        # INITIAL SETUP
        # -------------
        # Check that arguments have acceptable values
        if i0 > i1:
            raise ValueError("i0 must be less than or equal to i1")
        elif n0 > n1:
            raise ValueError("n0 must be less than or equal to n1")
        elif di <= 0:
            raise ValueError("di must be greater than zero")
        elif dn <= 0:
            raise ValueError("dn must be greater than zero")
        elif (not ((type(materials) == Material) or (type(materials) is tuple))) or (
                (type(materials) is tuple) and (len(materials) != 0) and (type(materials[0]) != Material)):
            raise TypeError("materials must be either a Material object or a tuple of Material objects")
        elif (not ((type(currents) == Current) or (type(currents) is tuple))) or (
                (type(currents) is tuple) and (len(currents) != 0) and (type(currents[0]) != Current)):
            raise TypeError("currents must be either a Current object or a tuple of Current objects")
        # Determine the number of temporal and spatial cells in the field
        self._nlen, self._ilen = Simulation.calc_dims(n0, n1, dn, i0, i1, di)
        # Save field dimensions and resolution
        self._i0 = i0
        self._i1 = i1
        self._di = di
        self._n0 = n0
        self._n1 = n1
        self._dn = dn
        # -------------
        # CURRENT SETUP
        # -------------
        # Put the currents variable into a tuple if it isn't already
        if type(currents) == Current:
            currents = (currents,)
        # Tuple already exits, create an empty current object
        elif len(currents) == 0:
            # Create an empty currents tuple
            c = np.zeros((1, 1))
            currents = (Current(self._nlen, self._ilen, 0, 0, c),)
        # Save the currents
        self._currents = currents
        # --------------
        # MATERIAL SETUP
        # --------------
        # Put the mat variable into a tuple if it isn't already
        if type(materials) == Material:
            materials = (materials,)
        # Tuple already exits, create an non-interacting material
        elif len(materials) == 0:
            # Create an empty material
            materials = (EmptyMaterial(self._di, self._dn, self._ilen, self._nlen),)
        # Save the material
        self._materials = materials
        # --------------
        # BOUNDARY SETUP
        # --------------
        # Setup boundary condition
        self._boundary = boundary
        if self._boundary == 'absorbing':
            self._eprev0 = np.complex64(0)
            self._eprev1 = np.complex64(0)
            self._erprev0 = np.complex64(0)
            self._erprev1 = np.complex64(0)
        # -----------
        # FIELD SETUP
        # -----------
        # Create each field
        self._efield = np.zeros(self._ilen, dtype=np.complex64)
        self._hfield = np.zeros(self._ilen, dtype=np.complex64)
        # Create each reference field
        self._efieldr = np.zeros(self._ilen, dtype=np.complex64)
        self._hfieldr = np.zeros(self._ilen, dtype=np.complex64)
        # ---------------
        # CONSTANTS SETUP
        # ---------------
        # Save constants
        self._epsilon0 = epsilon0
        self._mu0 = mu0
        # -------------------
        # STORED VALUES SETUP
        # -------------------
        # Save nstore info
        self._nstore = nstore
        self._nstore_len = len(self._nstore)
        # Check to see if any time index stores are requested
        if self._nstore_len != 0:
            # Create arrays to store the field values in each location
            self._nstore_efield = np.zeros((self._nstore_len, self._ilen), dtype=np.complex64)
            self._nstore_hfield = np.zeros((self._nstore_len, self._ilen), dtype=np.complex64)
            self._nstore_efieldr = np.zeros((self._nstore_len, self._ilen), dtype=np.complex64)
            self._nstore_hfieldr = np.zeros((self._nstore_len, self._ilen), dtype=np.complex64)
        # Save istore info
        self._istore = istore
        self._istore_len = len(self._istore)
        # Check to see if any location index stores are requested
        if self._istore_len != 0:
            # Create arrays to store the field values in each location
            self._istore_efield = np.zeros((self._nlen, self._istore_len), dtype=np.complex64)
            self._istore_hfield = np.zeros((self._nlen, self._istore_len), dtype=np.complex64)
            self._istore_efieldr = np.zeros((self._nlen, self._istore_len), dtype=np.complex64)
            self._istore_hfieldr = np.zeros((self._nlen, self._istore_len), dtype=np.complex64)

    def simulate(self, tqdmarg={}):
        """
        Executes the simulation.

        :param tqdmarg: The arguments to pass the tdqm iterator (lookup arguments on the tqdm documentation)
        """
        # Iterate through all materials and reset each so that prior simulation information isn't held in the material.
        for mat in self._materials:
            mat.reset_material()
        # Create a counter for the nstore index
        nstore_index = 0
        # Simulate by iterating over the simulation length
        for n in tqdm(range(self._nlen), **tqdmarg):
            # Update materials
            self._update_materials(n)
            # Update coefficients
            self._update_coefficients()
            # Compute H-field and update
            self._update_hfield()
            self._update_hfieldr()
            # Compute E-field and update
            self._update_efield(n)
            self._update_efieldr(n)
            # Apply boundary conditions
            if self._boundary == 'zero':  # Zero boundary condition
                pass  # No necessary action
            if self._boundary == 'absorbing':  # Absorbing boundary condition
                # Set the field values at the boundary to the previous value one away from the boundary, this somehow
                # results in absorption, I'm not really sure how... I think it has something to do with preventing any
                # wave reflection, meaning that the field values just end up going to zero. It would be a good idea to
                # ask Ben about this.
                self._efield[0] = self._eprev0
                self._efield[-1] = self._eprev1
                self._efieldr[0] = self._erprev0
                self._efieldr[-1] = self._erprev1
                # Save the field values one away from each boundary for use next iteration
                self._eprev0 = self._efield[1]
                self._eprev1 = self._efield[-2]
                self._erprev0 = self._efieldr[1]
                self._erprev1 = self._efieldr[-2]
            # Save the the fields if at the correct index
            if self._nstore.count(n) == 1:
                self._nstore_hfield[nstore_index] = self._hfield
                self._nstore_efield[nstore_index] = self._efield
                self._nstore_hfieldr[nstore_index] = self._hfieldr
                self._nstore_efieldr[nstore_index] = self._efieldr
                nstore_index += 1
            # Save specific field locations if storing has been requested
            if self._istore_len != 0:
                # Store each location
                self._istore_hfield[n] = self._efield[self._istore]
                self._istore_efield[n] = self._efieldr[self._istore]
                self._istore_hfieldr[n] = self._hfield[self._istore]
                self._istore_efieldr[n] = self._hfieldr[self._istore]

    def _update_hfield(self):
        """
        Updates the H-field to the values at the next iteration. Should be called once per simulation step.
        """
        h_t1 = self._hfield[:-1]
        h_t2 = self._coeff_h1 * (self._efield[1:] - self._efield[:-1])
        self._hfield[:-1] = h_t1 - h_t2

    def _update_efield(self, n):
        """
        Updates the E-field to the values at the next iteration. Should be called once per simulation step.

        :param n: The current temporal index of the simulation.
        """
        e_t1 = self._coeff_e0[1:] * self._efield[1:]
        e_t2 = self._coeff_e1[1:] * self._compute_psi()[1:]
        e_t3 = self._coeff_e2[1:] * (self._hfield[1:] - self._hfield[:-1])
        e_t4 = self._coeff_e3[1:] * self._get_current(n)[1:]
        self._efield[1:] = e_t1 + e_t2 - e_t3 - e_t4

    def _update_hfieldr(self):
        """
        Updates the reference H-field to the values at the next iteration. Should be called once per simulation step.
        """
        h_t1 = self._hfieldr[:-1]
        h_t2 = self._coeff_h1r * (self._efieldr[1:] - self._efieldr[:-1])
        self._hfieldr[:-1] = h_t1 - h_t2

    def _update_efieldr(self, n):
        """
        Updates the reference E-field to the values at the next iteration. Should be called once per simulation step.
        
        :param n: The current temporal index of the simulation.
        """
        e_t1 = self._coeff_e0r * self._efieldr[1:]
        e_t3 = self._coeff_e2r * (self._hfieldr[1:] - self._hfieldr[:-1])
        e_t4 = self._coeff_e3r * self._get_current(n)[1:]
        self._efieldr[1:] = e_t1 - e_t3 - e_t4

    def _update_coefficients(self):
        """
        Computes the coefficients for each update term based on the current Material values.
        """
        # Sum the epsiloninf values of each material at the current time to get the final epsiloninf array
        epsiloninf = np.zeros(self._ilen, dtype=np.complex64)
        for mat in self._materials:
            epsiloninf = np.add(epsiloninf, mat.get_epsiloninf())
        # Sum the chi0 values of each material to get the final epsiloninf array
        chi0 = np.zeros(self._ilen, dtype=np.complex64)
        for mat in self._materials:
            chi0 = np.add(chi0, mat.get_chi0())
        # Calculate simulation proportionality constants
        self._coeff_e0 = epsiloninf / (epsiloninf + chi0)
        self._coeff_e1 = 1.0 / (epsiloninf + chi0)
        self._coeff_e2 = self._dn / (self._epsilon0 * self._di * (epsiloninf + chi0))
        self._coeff_e3 = self._dn / (self._epsilon0 * (epsiloninf + chi0))
        self._coeff_h1 = self._dn / (self._mu0 * self._di)
        # Create simulation reference proportionality constants (the reference sees chi0=0 and epsiloninf=1)
        self._coeff_e0r = np.complex64(1)
        self._coeff_e2r = self._dn / (self._epsilon0 * self._di)
        self._coeff_e3r = self._dn / self._epsilon0
        self._coeff_h1r = self._dn / (self._mu0 * self._di)

    def _get_current(self, n):
        """
        Calculates the current at all points in the simulation using all the currents in the simulation

        :param n: The temporal index :math:`n` to calculate the current at
        """
        # Create an array to hold the current
        current = np.zeros(self._ilen)
        for c in self._currents:
            current = np.add(current, c.get_current(n))
        # Return
        return current

    def _compute_psi(self):
        """
        Calculates psi at all points in the simulation using all materials in the simulation.
        """
        # Create an array to hold psi
        psi = np.zeros(self._ilen)
        for mat in self._materials:
            psi = np.add(psi, mat.get_psi())
        # Return
        return psi

    def _update_materials(self, n):
        """
        Updates the each material in the simulation using the `_update_mat` function. Should be called once per
        simulation step.
        """
        # Iterate through all materials and update each
        for mat in self._materials:
            mat.update_material(n, self._efield)

    def get_dims(self):
        """
        Returns the dimensions of the simulation.

        :returns: A tuple :code:`(ilen, nlen)` containing the spatial and temporal dimensions in cells
        """
        return self._ilen, self._nlen

    def get_materials(self):
        """
        Returns the tuple of Material objects present in the simulation.

        :returns: A tuple of Material objects
        """
        return self._materials

    def export_nfields(self):
        """
        Exports the field values at temporal indices specified by nstore at the Simulation object's initialization,
        where an index along axis=0 corresponds to the corresponding temporal index in nstore. Values along axis=1
        correspond to the spatial index.

        :return: `(hfield, efield, hfieldr, efieldr)` where the suffix `r` corresponds to a reference field. If nstore
        is unspecified returns None
        """
        if self._nstore_len == 0:
            return None
        else:
            return self._nstore_hfield, self._nstore_efield, self._nstore_hfieldr, self._nstore_efieldr

    def export_ifields(self):
        """
        Exports the field values at spatial indices specified by istore at the Simulation object's initialization,
        where an index along axis=1 corresponds to the corresponding spatial index in istore. Values along axis=0
        correspond to the temporal index.

        :return: `(hfield, efield, hfieldr, efieldr)` where the suffix `r` corresponds to a reference field. If istore
        is unspecified returns None
        """
        if self._istore_len == 0:
            return None
        else:
            return self._istore_hfield, self._istore_efield, self._istore_hfieldr, self._istore_efieldr

    @staticmethod
    def calc_dims(i0, i1, di, n0, n1, dn):
        """
        Calculates the dimensions of the simulation in cells.

        :param i0: The spatial value at which the field starts
        :param i1: The spatial value at which the field ends
        :param di: The spatial step size
        :param n0: The temporal value at which the field starts
        :param n1: The temporal value at which the field ends
        :param dn: The temporal step size
        :return: A tuple `(ilen, nlen)` of the spatial and temporal dimensions
        """
        nlen = int(np.floor((n1 - n0) / dn))
        ilen = int(np.floor((i1 - i0) / di) + 2)  # Add two to account for boundary conditions
        return ilen, nlen

    @staticmethod
    def calc_arrays(i0, i1, di, n0, n1, dn):
        """
        Calculates spatial and time arrays of the same dimensions of the simulation. Array values are populated by their
        the spatial and temporal values at their respective simulation spatial and temporal indices.

        :param i0: The spatial value at which the field starts
        :param i1: The spatial value at which the field ends
        :param di: The spatial step size
        :param n0: The temporal value at which the field starts
        :param n1: The temporal value at which the field ends
        :param dn: The temporal step size
        :return: A tuple `(z, t)` of the spatial and temporal arrays
        """
        # Calculate simulation dimensions
        ilen, nlen = Simulation.calc_dims(i0, i1, di, n0, n1, dn)
        # Create z and t arrays
        z = np.linspace(i0 + di / 2, i1 + di / 2, ilen, endpoint=False)
        t = np.linspace(n0 + dn / 2, n1 + dn / 2, nlen, endpoint=False)
        # Return
        return z, t


class Current:
    r"""
    The Current class is used to represent a current in the simulation.

    :param nlen: The number of temporal indices in the simulation
    :param ilen: The number of spatial indices in the simulation
    :param n0: The starting temporal index of the current
    :param i0: The starting spatial index of the current
    :param current: A matrix representing the current, where axis=0 represents locations in time :math:`n` and axis=1
    represents locations in space :math:`i`
    """

    def __init__(self, nlen, ilen, n0, i0, current):
        # -------------
        # INITIAL SETUP
        # -------------
        # Save arguments
        self._nlen = nlen
        self._ilen = ilen
        self._n0 = n0
        self._i0 = i0
        # Get and save material dimension info
        if len(np.shape(current)) > 1:
            self._cnlen = np.shape(current)[0]
            self._cilen = np.shape(current)[1]
        else:
            self._cnlen = np.shape(current)[0]
            self._cilen = 1
        # Check for error
        if self._n0 < 0 or self._n0 + self._cnlen > self._nlen:
            raise ValueError("Current cannot start at n=" + str(self._n0) + " and end at n=" + str(
                self._n0 + self._cnlen) + " as this exceeds the dimensions of the simulation.")
        elif self._i0 < 0 or self._i0 + self._cilen > self._ilen:
            raise ValueError("Current cannot start at i=" + str(self._i0) + " and end at i=" + str(
                self._i0 + self._cilen) + " as this exceeds the dimensions of the simulation.")
        # Reshape the current array so that it can be indexed correctly
        self._current = np.reshape(current, (self._cnlen, self._cilen))

    def get_current(self, n):
        """
        Returns the current at time index :math:`n` as an array the length of the simulation
        """
        # Determine if n is within the bounds of the current array
        if n < self._n0 or (self._n0 + self._cnlen) <= n:
            # Not in bounds, return zero-valued array
            return np.zeros(self._cilen, dtype=np.complex64)
        # Pad the current array so that it spans the length of the simulation
        current_padded = np.pad(self._current[n - self._n0], (self._i0, self._ilen - (self._i0 + self._cilen)),
                                'constant')
        # Return
        return current_padded


class Material(ABC):
    r"""
    The Material class is an abstract class that defines the minimum requirements for a Material object to have in the
    simulation. All Materials in the simulation must inherit Material.

    :param di: The spatial time step of the simulation
    :param dn: The temporal step size of the simulation
    :param ilen: The number of spatial indices in the simulation
    :param nlen: The number of temporal indices in the simulation
    :param material_i0: The starting spatial index of the material
    :param material_i1: The ending spatial index of the material
    :param material_n0: The starting temporal index of the material
    :param material_n1: The ending temporal index of the material
    """

    def __init__(self, di, dn, ilen, nlen, material_i0, material_i1, material_n0, material_n1):
        # Call super
        super().__init__()
        # -------------
        # INITIAL SETUP
        # -------------
        # Check for errors
        if material_i1 <= material_i0:
            raise ValueError(
                'The material spatial ending index must be greater than the material spatial starting index')
        elif material_n1 <= material_n0:
            raise ValueError(
                'The material temporal ending index must be greater than the material temporal starting index')
        elif material_i1 - material_i0 > ilen:
            raise ValueError('The material spatial length cannot be greater than the simulation spatial length')
        elif material_n1 - material_n0 > nlen:
            raise ValueError('The material temporal length cannot be greater than the simulation temporal length')
        # Save function arguments
        self._di = di
        self._dn = dn
        self._ilen = ilen
        self._nlen = nlen
        self._material_i0 = material_i0
        self._material_n0 = material_n0
        self._material_ilen = material_i1 - material_i0
        self._material_nlen = material_n1 - material_n0

    @abstractmethod
    def reset_material(self):
        """
        This function is called before each simulation. It should reset any material values that are calculated during
        the simulation to their initial values.
        """
        pass

    @abstractmethod
    def update_material(self, n, efield):
        """
        This function is called at the start of each simulation time step. It should update the :math:`\chi` and
        :math:`\psi` values of the material to their values at n.

        :param n: The current temporal index of the simulation.
        :param efield: The previous electric field of the simulation.
        """
        pass

    @abstractmethod
    def get_chi0(self):
        """
        Returns the value of :math:`\chi_0` at the current time step in the simulation at each spatial location in the
        simulation.

        :return: The current value of :math:`\chi_0` at each spatial location in the simulation
        """
        pass

    @abstractmethod
    def get_epsiloninf(self):
        """
        Returns the value of :math:`\epsilon_\infty` at the current time step in the simulation at each spatial location
        in the simulation.

        :return: The current value of :math:`\epsilon_\infty` at each spatial location in the simulation
        """
        pass

    @abstractmethod
    def get_psi(self):
        """
        Returns the value of :math:`\psi` at the current time step in the simulation at each spatial location in the
        simulation.

        :return: The current value of :math:`\psi` at each spatial location in the simulation
        """
        pass


class EmptyMaterial(Material):
    """
    Represents an empty Material, or in other words vacuum
    """

    def __init__(self, di, dn, ilen, nlen):
        # Call super
        super().__init__(di, dn, ilen, nlen, 0, 1, 0, 1)

    def update_material(self, n, efield):
        # Do nothing
        pass

    def get_chi0(self):
        # Simply return 0
        return np.zeros(self._ilen, dtype=np.complex64)

    def get_epsiloninf(self):
        # Simply return 1
        return np.ones(self._ilen, dtype=np.complex64)

    def get_psi(self):
        # Simply return 0
        return np.zeros(self._ilen, dtype=np.complex64)

    def reset_material(self):
        # Do nothing
        pass


class StaticMaterial(Material):
    """
    The StaticMaterial class allows for the simulation of a static material, that is a material that has a constant
    definition of electric susceptibility in time. The electric susceptibility is modeled using a harmonic oscillator.

    :param di: The spatial time step of the simulation
    :param dn: The temporal step size of the simulation
    :param ilen: The number of spatial indices in the simulation
    :param nlen: The number of temporal indices in the simulation
    :param material_i0: The starting spatial index of the material
    :param a1: A matrix representing :math:`A_1` where axis=0 represents the :math:`j` th oscillator and axis=1
    represents the :math:`i` th spatial index
    :param a2: A matrix representing :math:`A_2` where axis=0 represents the :math:`j` th oscillator and axis=1
    represents the :math:`i` th spatial index
    :param g: A matrix representing :math:`\gamma` where axis=0 represents the :math:`j` th oscillator and axis=1
    represents the :math:`i` th spatial index
    :param b: A matrix representing :math:`\beta` where axis=0 represents the :math:`j` th oscillator and axis=1
    represents the :math:`i` th spatial index
    :param opacity: A vector representing the opacity of the material in time. Each index corresponds to the
    :math:`n` th time index of the material where `1` corresponds to the material being opaque and `0` corresponds to
    the material being transparent. Values can be real numbers. Defaults to an opaque material for all time.
    :param istore: A tuple of spatial indices to save :math:`\chi` values at in all points in time
    """

    def __init__(self, di, dn, ilen, nlen, material_i0, epsiloninf, a1, a2, g, b, opacity=None, istore=()):
        # -------------
        # INITIAL SETUP
        # -------------
        # Check for error
        if np.shape(a1) != np.shape(a2) or np.shape(a1) != np.shape(g) or np.shape(a1) != np.shape(b):
            raise ValueError("The dimensions of a1, a2, g, and b should be the same")
        elif (opacity is not None) and (len(np.shape(opacity)) != 1):
            raise ValueError("opacity should be a 1-dimensional Numpy array of length nlen or None type")
        elif (opacity is not None) and (np.shape(opacity)[0] != nlen):
            raise ValueError("opacity should be a Numpy array of length nlen or None type")
        # Get and save material dimension info
        if len(np.shape(a1)) > 1:
            self._jlen = np.shape(a1)[0]
            material_i1 = material_i0 + np.shape(a1)[1]
        else:
            self._jlen = 1
            material_i1 = material_i0 + np.shape(a1)[0]
        # Check for error
        if self._material_i0 < 0 or material_i1 > self._ilen:
            raise ValueError("Material cannot start at i=" + str(material_i0) + " and end at i=" + str(material_i1)
                             + " as this exceeds the dimensions of the simulation.")
        # Call super
        super().__init__(di, dn, ilen, nlen, material_i0, material_i1, 0, nlen)
        # If opacity is unspecified, set equal to opaque for all time, else save provided opacity
        if opacity is None:
            self._opacity = np.ones(self._nlen)
        else:
            self._opacity = opacity
        # Reshape arrays so that they can be indexed correctly
        self._a1 = np.reshape(a1, (self._jlen, self._material_ilen))
        self._a2 = np.reshape(a2, (self._jlen, self._material_ilen))
        self._g = np.reshape(g, (self._jlen, self._material_ilen))
        self._b = np.reshape(b, (self._jlen, self._material_ilen))
        # Epsilon_infinity is equal to one in vacuum, so only set self._epsiloninf equal to epsiloninf in the material
        epsiloninf_repeat = np.repeat(epsiloninf, self._material_ilen)
        self._epsiloninf = np.pad(epsiloninf_repeat,
                                  (self._material_i0, self._ilen - (self._material_i0 + self._material_ilen)),
                                  'constant', constant_values=1)
        # --------------
        # MATERIAL SETUP
        # --------------
        # Calculate susceptibility beta and gamma sums and exponents
        b_min_g = np.add(self._b, -self._g)
        min_b_min_g = np.add(-self._b, -self._g)
        self._exp_1 = np.exp(np.multiply(b_min_g, self._dn))
        self._exp_2 = np.exp(np.multiply(min_b_min_g, self._dn))
        # Calculate initial susceptibility values
        self._chi0_1 = np.zeros((self._jlen, self._material_ilen), dtype=np.complex64)
        self._chi0_2 = np.zeros((self._jlen, self._material_ilen), dtype=np.complex64)
        for j in range(self._jlen):
            for mi in range(self._material_ilen):
                if np.abs(b_min_g[j, mi]) < 1e-5:
                    # beta-gamma is small, avoid divide by zero error
                    self._chi0_1[j, mi] = self._a1[j, mi] * self._dn
                    self._chi0_2[j, mi] = np.multiply(np.divide(self._a2[j, mi], min_b_min_g[j, mi]),
                                                      np.subtract(self._exp_2[j, mi], 1))
                else:
                    # beta-gamma is not small, calculate normally
                    self._chi0_1[j, mi] = np.multiply(np.divide(self._a1[j, mi], b_min_g[j, mi]),
                                                      np.subtract(self._exp_1[j, mi], 1))
                    self._chi0_2[j, mi] = np.multiply(np.divide(self._a2[j, mi], min_b_min_g[j, mi]),
                                                      np.subtract(self._exp_2[j, mi], 1))
        # Calculate first delta susceptibilityy values
        self._dchi0_1 = np.multiply(self._chi0_1, np.subtract(1, self._exp_1))
        self._dchi0_2 = np.multiply(self._chi0_2, np.subtract(1, self._exp_2))
        # Initialize psi values to zero
        self._psi_1 = np.zeros((self._jlen, self._material_ilen), dtype=np.complex64)
        self._psi_2 = np.zeros((self._jlen, self._material_ilen), dtype=np.complex64)
        # Calculate chi0
        chi0_j = np.add(self._chi0_1, self._chi0_2)
        chi0_summed = np.sum(chi0_j, axis=0)
        # Pad chi0 so that it spans the length of the simulation
        self._chi0 = np.pad(chi0_summed, (self._material_i0, self._ilen - (self._material_i0 + self._material_ilen)),
                            'constant')
        # Create a place to store susceptibility values
        self._chi_1 = np.copy(self._chi0_1)
        self._chi_2 = np.copy(self._chi0_2)
        # -------------------
        # STORED VALUES SETUP
        # -------------------
        # Save istore info
        self._istore = istore
        self._istore_len = len(self._istore)
        # Check to see if any istores are requested
        if self._istore_len != 0:
            # Create arrays to store the field values in each location
            self._istore_chi = np.zeros((self._nlen, self._istore_len), dtype=np.complex64)

    def reset_material(self):
        # Reset psi
        self._psi_1 = np.zeros((self._jlen, self._material_ilen), dtype=np.complex64)
        self._psi_2 = np.zeros((self._jlen, self._material_ilen), dtype=np.complex64)
        # Reset chi
        self._chi_1 = self._chi0_1
        self._chi_2 = self._chi0_2
        # Reset istore_chi
        if self._istore_len != 0:
            # Create arrays to store the field values in each location
            self._istore_chi = np.zeros((self._nlen, self._istore_len), dtype=np.complex64)

    def update_material(self, n, efield):
        """
        Updates the values of :math:`\psi` and :math:`\chi` Saves the values of :math:`chi` requested via the `istore`
        parameter.

        :param n: The iteration index :math:`n`
        :param efield: The efield to use in update calculations
        """
        # Update psi
        self._update_psi(efield)
        # Update chi_1 and chi_2
        self._chi_1 = np.multiply(self._chi_1, self._exp_1)
        self._chi_2 = np.multiply(self._chi_2, self._exp_2)
        # Save specific field locations if storing has been requested
        if self._istore_len != 0:
            # Add chi_1 and chi_2 to yield chi for each oscillator at each location specified by istore
            chi_j = np.add(self._chi_1[self._istore], self._chi_2[self._istore])
            # Sum across all oscillators to determine chi and store
            self._istore_chi[n] = np.sum(chi_j, axis=0)

    # TODO Implement _update_psi(efield) and all below
    def _update_psi(self, efield):
        """
        Updates the value of psi_1 and psi_2. Should be called once per simulation step.

        :param efield: The efield to use in update calculations
        """
        # Copy the efield so that instead of being a vector it is a matrix composed of horizontal efield vectors
        e = np.tile(efield[self._mat0:self._mat0 + self._matlen], (self._jlen, 1))
        # Calculate first term
        t1_1 = np.multiply(e, self._dchi0_1)
        t1_2 = np.multiply(e, self._dchi0_2)
        # Calculate second term
        t2_1 = np.multiply(self._psi_1, self._exp_1)
        t2_2 = np.multiply(self._psi_2, self._exp_2)
        # Update next psi values
        self._psi_1 = np.add(t1_1, t2_1)
        self._psi_2 = np.add(t1_2, t2_2)

    def get_chi0(self):
        pass

    def get_epsiloninf(self):
        pass

    def get_psi(self):
        pass


# TODO Implement DynamicMat, two possible methods of numerical integration? Symbolic (preferred?) vs numerical?

class Mat:
    r"""
    The Mat class is used to represent a material present in a simulation

    :param dn: The temporal step size
    :param ilen: The number of spatial indicies in the simulation
    :param nlen: The number of temporal indicies in the simulation
    :param timebounds: A tuple `(timeStart, timeEnd)` of the time indicies between which the material exists in the simulation where `timeStart` is inclusive and `timeEnd` is exclusive. Multiple materials with carefully chosen time bounds can be used to change material properties in time.
    :param mat0: The starting index of the material
    :param epsiloninf: :math:`\epsilon_\infty` inside the material
    :param mata1: A matrix representing :math:`A_1` where axis=0 represents the :math:`j` th oscillator and axis=1 represents the :math:`i` th spatial index
    :param mata2: A matrix representing :math:`A_2` where axis=0 represents the :math:`j` th oscillator and axis=1 represents the :math:`i` th spatial index
    :param matg: A matrix representing :math:`\gamma` where axis=0 represents the :math:`j` th oscillator and axis=1 represents the :math:`i` th spatial index
    :param matb: A matrix representing :math:`\beta` where axis=0 represents the :math:`j` th oscillator and axis=1 represents the :math:`i` th spatial index
    :param opacity: A vector representing the opacity of the material in time. Each index corresponds to the :math:`n` th time index of the material where `1` corresponds to the material being opaque and `0` corresponds to the material being transparent. Defaults to an opaque material for all time.
    :param storelocs: A list of locations to save chi at during each step in time, indexed from 0 to the material length
    :param dtype: The data type to store the field values in
    """

    def __init__(self, dn, ilen, nlen, mat0, epsiloninf, mata1, mata2, matg, matb, opacity=None, storelocs=[],
                 dtype=np.complex64):
        # -------------
        # INITIAL SETUP
        # -------------
        # Check for error
        if np.shape(mata1) != np.shape(mata2) or np.shape(mata1) != np.shape(matg) or np.shape(mata1) != np.shape(matb):
            raise ValueError("The dimensions of mata1, mata2, matg, and matb should be the same")
        elif (opacity is not None) and (len(np.shape(opacity)) != 1):
            raise ValueError("opacity should be a 1-dimensional Numpy array of length nlen")
        elif (opacity is not None) and (np.shape(opacity)[0] != nlen):
            raise ValueError("opacity should be a Numpy array of length nlen")
        # Save arguments
        self._dn = dn
        self._ilen = ilen
        self._nlen = nlen
        self._mat0 = mat0
        self._dtype = dtype
        # If opacity is unspecified, set equal to opaque for all time, else save provided opacity
        if opacity is None:
            self._opacity = np.ones(self._nlen)
        else:
            self._opacity = opacity
        # Get and save material dimension info
        if len(np.shape(mata1)) > 1:
            self._jlen = np.shape(mata1)[0]
            self._matlen = np.shape(mata1)[1]
        else:
            self._jlen = 1
            self._matlen = np.shape(mata1)[0]
        # Check for error
        if self._mat0 < 0 or self._mat0 + self._matlen > self._ilen:
            raise ValueError("Material cannot start at i=" + str(self._mat0) + " and end at i=" + str(
                self._mat0 + self._matlen) + " as this exceeds the dimensions of the simulation.")
        # Reshape arrays so that they can be indexed correctly
        self._mata1 = np.reshape(mata1, (self._jlen, self._matlen))
        self._mata2 = np.reshape(mata2, (self._jlen, self._matlen))
        self._matg = np.reshape(matg, (self._jlen, self._matlen))
        self._matb = np.reshape(matb, (self._jlen, self._matlen))
        del mata1
        del mata2
        del matg
        del matb
        # Epsilon_infinity is equal to one in vacuum, so only set self._epsiloninf equal to epsiloninf in the material
        epsiloninf_repeat = np.repeat(epsiloninf, self._matlen)
        self._epsiloninf = np.pad(epsiloninf_repeat, (self._mat0, self._ilen - (self._mat0 + self._matlen)), 'constant',
                                  constant_values=1)
        # --------------
        # MATERIAL SETUP
        # --------------
        # Calculate susceptability beta and gamma sums and exponents
        b_min_g = np.add(self._matb, -self._matg)
        min_b_min_g = np.add(-self._matb, -self._matg)
        self._exp_1 = np.exp(np.multiply(b_min_g, self._dn))
        self._exp_2 = np.exp(np.multiply(min_b_min_g, self._dn))
        # Calculate initial susceptability values
        self._chi0_1 = np.zeros((self._jlen, self._matlen), dtype=self._dtype)  # Set chi0_1=0 initially
        self._chi0_2 = np.zeros((self._jlen, self._matlen), dtype=self._dtype)  # Set chi0_2=0 initially
        for j in range(self._jlen):
            for mi in range(self._matlen):
                if np.abs(b_min_g[j, mi]) < 1e-5:
                    # beta-gamma is small, avoid divide by zero error
                    self._chi0_1[j, mi] = self._mata1[j, mi] * self._dn
                    self._chi0_2[j, mi] = np.multiply(np.divide(self._mata2[j, mi], min_b_min_g[j, mi]),
                                                      np.subtract(self._exp_2[j, mi], 1))
                else:
                    # beta-gamma is not small, calculate normally
                    self._chi0_1[j, mi] = np.multiply(np.divide(self._mata1[j, mi], b_min_g[j, mi]),
                                                      np.subtract(self._exp_1[j, mi], 1))
                    self._chi0_2[j, mi] = np.multiply(np.divide(self._mata2[j, mi], min_b_min_g[j, mi]),
                                                      np.subtract(self._exp_2[j, mi], 1))
        # Calclate first delta susceptabiility values
        self._dchi0_1 = np.multiply(self._chi0_1, np.subtract(1, self._exp_1))
        self._dchi0_2 = np.multiply(self._chi0_2, np.subtract(1, self._exp_2))
        # Initialize psi values to zero
        self._psi_1 = np.zeros((self._jlen, self._matlen), dtype=self._dtype)
        self._psi_2 = np.zeros((self._jlen, self._matlen), dtype=self._dtype)
        # Calculate chi0
        chi0_j = np.add(self._chi0_1, self._chi0_2)
        chi0 = np.sum(chi0_j, axis=0)
        # Pad chi0 so that it spans the length of the simulation
        chi0_padded = np.pad(chi0, (self._mat0, self._ilen - (self._mat0 + self._matlen)), 'constant')
        self._chi0 = chi0_padded
        # -------------------
        # STORED VALUES SETUP
        # -------------------
        # Save storeloc info
        self._storelocs = storelocs
        self._nlocs = len(self._storelocs)
        # Check to see if any storelocs are requested
        if self._nlocs != 0:
            # Create arrays to store the field values in each location
            self._locs = np.zeros((self._nlen, self._nlocs), dtype=self._dtype)
        # ---------------------
        # CHI CALCULATION SETUP
        # ---------------------
        # Save the chi0 values from chi0_1 and chi0_2 from the indicies we wish to store at all j values
        self._prev_chi_1 = self._chi0_1[:, self._storelocs]
        self._prev_chi_2 = self._chi0_2[:, self._storelocs]

    def __eq__(self, other):
        """
        Tests for equality between this Material object and another. This does not account for the current state of the object, but rather its initial conditions.
        """
        if isinstance(other, Mat):
            """dn, ilen, nlen, mat0, epsiloninf, mata1, mata2, matg, matb"""
            dn_eq = (self._dn == other._dn)
            ilen_eq = (self._ilen == other._ilen)
            nlen_eq = (self._nlen == other._nlen)
            mat0_eq = (self._mat0 == other._mat0)
            epsiloninf_eq = (self._epsiloninf == other._epsiloninf)
            mata1_eq = np.array_equal(self._mata1, other._mata1)
            mata2_eq = np.array_equal(self._mata2, other._mata2)
            matg_eq = np.array_equal(self._matg, other._matg)
            matb_eq = np.array_equal(self._matb, other._matb)
            return (
                    dn_eq and ilen_eq and nlen_eq and mat0_eq and epsiloninf_eq and mata1_eq and mata2_eq and matg_eq and matb_eq)
        return False

    def get_pos(self):
        r"""
        Returns a Tuple contianing a Numpy array of value 0 outside of the material and 1 inside of the material, time0, and time1.

        :return: `(arr, time0, time1)`
        """
        return (np.pad(np.repeat(1, self._matlen), (self._mat0, self._ilen - (self._mat0 + self._matlen)), 'constant'),
                self._time0, self._time1)

    def _update_chi(self):
        r"""
        Updates chi_1 and chi_2 (i.e. :math:`\chi_1` and :math:`\chi_2`) using the update equations :math:`\chi^{m+1}_{1,j}=\chi^m_{1,j}e^{\Delta t\left(-\gamma_j+\beta_j\right)}` and :math:`\chi^{m+1}_{2,j}=\chi^m_{2,j}e^{\Delta t\left(-\gamma_j-\beta_j\right)}`. Should be called once per simulation step.
        """
        # Extract the exponents at the j-values we are interested in updating
        exp_1 = self._exp_1[:, self._storelocs]
        exp_2 = self._exp_2[:, self._storelocs]
        # Calculate the updated chi_1 and chi_2
        update_chi_1 = np.multiply(self._prev_chi_1, exp_1)
        update_chi_2 = np.multiply(self._prev_chi_2, exp_2)
        # Save the update_chi_1 and update_chi_2 into the prev_chi_1 and prev_chi_2 values
        self._prev_chi_1 = update_chi_1
        self._prev_chi_2 = update_chi_2

    def _compute_chi(self):
        r"""
        Computes chi at the points specified in the simulation by the `storelocs` parameter via :math:`\chi^n=\Re\left[\chi^n_1e^{\Delta t(-\gamma_j+\beta_j)} + \chi^n_2e^{\Delta t(-\gamma_j-\beta_j)}\right]`.

        :return: :math:`\chi^n` where :math:`n` is the :math:`n` th call to the function `_update_chi`
        """
        # Extract the exponents at the j-values we wish to store
        exp_1 = self._exp_1[:, self._storelocs]
        exp_2 = self._exp_2[:, self._storelocs]
        # Compute chi_1 and chi_2
        t1 = np.multiply(self._prev_chi_1, exp_1)
        t2 = np.multiply(self._prev_chi_2, exp_2)
        # Add chi_1 and chi_2 to yield chi for each oscillator
        chi_j = np.add(t1, t2)
        # Sum across all oscillators to determine chi at each location specified by storelocs
        chi = np.sum(chi_j, axis=0)
        # Return
        return chi

    def _get_epsiloninf(self):
        r"""
        Returns the high frequency susceptability of the material :math:`\epsilon_\infty`.

        :return: A Numpy array of length :code:`ilen` of value 1 outside of the material and :math:`\epsilon_\infty` inside of the material
        """
        return self._epsiloninf

    def _get_chi0(self):
        r"""
        Returns the initial susceptibility of the material :math:`\chi_0`.

        :return: A Numpy array of length :code:`ilen` of value 0 outside of the material and :math:`\chi_0` inside of the material
        """
        # Return the real part as specified in Beard
        return np.real(self._chi0)

    def _compute_psi(self, n):
        """
        Calculates psi at all points in the simulation using the current value of psi_1 and psi_2. Scaled by the `opacity` array passed in at initialization.

        :param n: The current temporal index of the simulation.
        """
        # Find the psi matrix
        psi_j = np.add(self._psi_1, self._psi_2)
        # Sum the psi matrix along axis=0 to combine all oscillators
        psi = np.sum(psi_j, axis=0)
        # Pad the psi array so that it spans the length of the simulation
        psi_padded = np.pad(psi, (self._mat0, self._ilen - (self._mat0 + self._matlen)), 'constant')
        # Return the real part as specified in Beard
        return np.real(psi_padded * self._opacity[n])

    def _update_psi(self, efield):
        """
        Updates the value of psi_1 and psi_2. Should be called once per simulation step.

        :param efield: The efield to use in update calculations
        """
        # Copy the efield so that instead of being a vector it is a matrix composed of horizontal efield vectors
        e = np.tile(efield[self._mat0:self._mat0 + self._matlen], (self._jlen, 1))
        # Calculate first term
        t1_1 = np.multiply(e, self._dchi0_1)
        t1_2 = np.multiply(e, self._dchi0_2)
        # Calculate second term
        t2_1 = np.multiply(self._psi_1, self._exp_1)
        t2_2 = np.multiply(self._psi_2, self._exp_2)
        # Update next psi values
        self._psi_1 = np.add(t1_1, t2_1)
        self._psi_2 = np.add(t1_2, t2_2)

    def _update_mat(self, n, efield):
        """
        Updates the value of psi_1, psi_2, chi_1, and chi_2. Saves the values of chi requested via the `storelocs` parameter.

        :param n: The iteration index :math:`n`
        :param efield: The efield to use in update calculations
        """
        # Update psi and chi
        self._update_psi(efield)
        self._update_chi()
        # Save specific field locations if storing has been requested
        if self._nlocs != 0:
            # Store each location
            self._locs[n, :] = self._compute_chi()

    def _reset_mat(self):
        """
        Resets previously stored values of psi_1, psi_2, chi_1, and chi_2 to their initial values. Resets ensure that consecutive simulations on the same Mat object are independent of each other.
        """
        # Reset psi calculation
        self._psi_1 = np.zeros((self._jlen, self._matlen), dtype=self._dtype)
        self._psi_2 = np.zeros((self._jlen, self._matlen), dtype=self._dtype)
        # Reset previous chi values to chi0
        self._prev_chi_1 = self._chi0_1[:, self._storelocs]
        self._prev_chi_2 = self._chi0_2[:, self._storelocs]

    def export_locs(self):
        """
        Exports the value of chi at a specific location(s) (specified with :code:`storelocs` at initialization) at each point in time.

        :return: A tuple :code:`(ls, locs)` where :code:`ls` is the list :code:`storelocs` (the same :code:`storelocs` that is passed to the Simulation class during instantiation), :code:`locs` is a Numpy array containing chi at storelocs at each point in time (axis=0 is time and axis=1 is the respective storeloc location)
        """
        # Check to see if the value of each field at a specific location was saved over time
        if self._nlocs == 0:
            self._locs = None
        # Return
        return (self._storelocs, self._locs)