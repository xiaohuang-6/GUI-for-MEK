from multiprocessing import Pool
import numpy as np
import math
import matplotlib.pyplot as plt
from scipy import linalg
from collections import defaultdict as Dict


class Cofactor:
    """
    Represents a cofactor with a name and a list of redox potentials.
    """
    def __init__(self, name: str, redox: list):
        """
        Initialize a cofactor object with its name and redox potentials.

        Args:
            name (str): Name of the cofactor.
            redox (list): List of ordered redox potentials.
        """
        self.name = name
        self.redox = redox  # Example: [first reduction potential, second reduction potential...]
        self.capacity = len(redox)  # The number of electrons the cofactor can occupy.

    def __str__(self) -> str:
        """
        String representation of the cofactor.

        Returns:
            str: Formatted string with cofactor details.
        """
        details = f"Cofactor Name: {self.name}\n"
        details += "------------\n"
        for i, potential in enumerate(self.redox):
            details += f"Redox State ID: {i}, Oxidation Potential: {potential}\n"
        return details


class Network:
    """
    Represents a network of cofactors with electron transfer functionalities.
    """
    def __init__(self):
        """
        Initialize an empty network.
        """
        # Network attributes
        self.num_cofactor = 0
        self.num_state = 1
        self.adj_num_state = 1
        self.allow = []
        self.id2cofactor = {}
        self.cofactor2id = {}
        self.adjacencyList = []
        self.D = None
        self.K = None
        self.siteCapacity = []
        self.num_reservoir = 0
        self.reservoirInfo = {}
        self.id2reservoir = {}
        self.reservoir2id = {}
        self.max_electrons = None
        self.min_electrons = None

        # ET parameters
        self.hbar = 6.5821 * 10 ** (-16)  # eV·s
        self.beta = 39.06  # 1/kT in 1/eV at room temperature
        self.reorgE = 0.7  # eV
        self.V = 0.01  # eV
        self.eps_r = 8 # relative dielectric constant

    def __str__(self) -> str:
        """
        String representation of the network.

        Returns:
            str: Formatted string with network details.
        """
        details = f"Total number of cofactors in the Network: {self.num_cofactor}\n"
        if self.num_cofactor == 0:
            details += "There are no cofactors in the Network. Please add cofactors first!\n"
            return details

        for idx, cofactor in self.id2cofactor.items():
            details += f"ID: {idx}\n"
            details += str(cofactor)

        if self.D is None:
            details += "------------\nAdjacency matrix not calculated yet!\n"
            return details

        details += "------------\nAdjacency matrix:\n"
        details += str(self.D)

        if self.num_reservoir > 0:
            details += f"------------\n{self.num_reservoir} reservoirs in the system.\n"
            for res_id, info in self.reservoirInfo.items():
                name, cofactor, redox_state, num_electron, deltaG, rate = info
                details += f"Reservoir ID: {res_id}, Name: {name}, Cofactor ID: {self.cofactor2id[cofactor]}, Redox State: {redox_state}\n"
                details += f"Electrons: {num_electron}, DeltaG: {deltaG}, Rate: {rate}\n"
        return details

    def addCofactor(self, cofactor: Cofactor):
        """
        Add a cofactor to the network.

        Args:
            cofactor (Cofactor): The cofactor to add.
        """
        self.num_state *= (cofactor.capacity + 1)
        self.id2cofactor[self.num_cofactor] = cofactor
        self.cofactor2id[cofactor] = self.num_cofactor
        self.siteCapacity.append(cofactor.capacity)
        self.num_cofactor += 1

    def addConnection(self, cof1: Cofactor, cof2: Cofactor, distance: float):
        """
        Connect two cofactors in the network.

        Args:
            cof1 (Cofactor): The first cofactor.
            cof2 (Cofactor): The second cofactor.
            distance (float): Distance between the two cofactors.
        """
        self.adjacencyList.append((self.cofactor2id[cof1], self.cofactor2id[cof2], distance))

    def addReservoir(self, name: str, cofactor: Cofactor, redox: int, num_electron: int, deltaG: float, rate: float):
        """
        Add a reservoir to the network.

        Args:
            name (str): Name of the reservoir.
            cofactor (Cofactor): The cofactor connected to the reservoir.
            redox (int): Redox state of the cofactor.
            num_electron (int): Number of electrons exchanged.
            deltaG (float): DeltaG for electron exchange.
            rate (float): Rate of electron exchange.
        """
        self.id2reservoir[self.num_reservoir] = name
        self.reservoir2id[name] = self.num_reservoir
        self.reservoirInfo[self.num_reservoir] = [name, cofactor, redox, num_electron, deltaG, rate]
        self.num_reservoir += 1

    def set_Max_Electrons(self, max_electrons: int):
        """
        Set the maximum number of electrons allowed in the network.

        Args:
            max_electrons (int): Maximum electrons.
        """
        self.max_electrons = max_electrons

    def set_Min_Electrons(self, min_electrons: int):
        """
        Set the minimum number of electrons allowed in the network.

        Args:
            min_electrons (int): Minimum electrons.
        """
        self.min_electrons = min_electrons

    def evolve(self, t: float, pop_init: np.array = None) -> np.array:
        """
        Evolve the population vector over a time step.

        Args:
            t (float): Time step.
            pop_init (np.array, optional): Initial population vector.

        Returns:
            np.array: Final population vector.
        """
        if pop_init is None:
            pop_init = np.zeros(self.adj_num_state)
            pop_init[0] = 1
        return linalg.expm(self.K * t) @ pop_init

    ####################################################
    ####  Core Functions for Building Rate Matrix   ####
    ####################################################

    # For the following functions, we make use of the internal labelling of the
    # states which uses one index which maps to the occupation number
    # representation [n1, n2, n3, ..., nN] and convert to idx in the rate
    # back and forth with state2idx() and idx2state() functions.
    def state2idx(self, state: list) -> int:
        """
        Given the list representation of the state, return index number in the main rate matrix
        Arguments:
            state {list} -- List representation of the state
        Returns:
            int -- Index number of the state in the main rate matrix
        """
        idx = 0
        N = 1
        for i in range(self.num_cofactor):
            idx += state[i] * N
            N *= (self.siteCapacity[i] + 1)

        return idx

    def idx2state(self, idx: int) -> list:
        """
        Given the index number of the state in the main rate matrix, return the list representation of the state
        Arguments:
            idx {int} -- Index number of the state in the main rate matrix
        Returns:
            list -- List representation of the state
        """
        state = []
        for i in range(self.num_cofactor):
            div = self.siteCapacity[i] + 1
            idx, num = divmod(idx, div)
            state.append(num)

        return state

    def constructStateList(self) -> list:
        """
        Go through all the possible states and make list of the subset with the allowed number of particles
        """
        self.allow = []
        if self.max_electrons == None:
            self.max_electrons = sum([site for site in self.siteCapacity])
        if self.min_electrons == None:
            self.min_electrons = 0
        for i in range(self.num_state):
            if sum(self.idx2state(i)) <= self.max_electrons and sum(self.idx2state(i)) >= self.min_electrons:
                self.allow.append(i)
        self.adj_num_state = len(self.allow)
#       print("adj_num_state",self.adj_num_state)
#       print("list:",self.allow)

    def getRate(self, kb: float, deltaG: float):
        # rate is the rate you will input in the addReservoir
        # kb is the rate of cofactor -> reservoir
        rate = kb * np.exp(-self.beta*deltaG)
        return rate
    
    def constructAdjacencyMatrix(self):
        """
        Construct the adjacency matrix from the adjacency list.
        """
        dim = self.num_cofactor
        self.D = np.zeros((dim, dim), dtype=float)
        for id1, id2, distance in self.adjacencyList:
            self.D[id1][id2] = self.D[id2][id1] = distance

    def constructRateMatrix(self, reorgE: float = 0.2):
        """
        Construct the rate matrix for electron transfer.

        Args:
            reorgE (float, optional): Reorganization energy.
        """
        self.K = np.zeros((self.adj_num_state, self.adj_num_state), dtype=float)
        for i in range(self.num_cofactor):
            for j in range(i + 1, self.num_cofactor):
                if self.D[i][j] != 0:
                    cof_i = self.id2cofactor[i]
                    cof_f = self.id2cofactor[j]
                    dis = self.D[i][j]
                    for donor_state in range(1, cof_i.capacity + 1):
                        for acceptor_state in range(cof_f.capacity):
                            deltaG = cof_i.redox[donor_state - 1] - cof_f.redox[acceptor_state]
                            k = self.ET(deltaG, dis, reorgE, self.beta, self.V)
                            self.connectStateRate(i, donor_state, j, acceptor_state, k, deltaG, 1)
        for res_id, info in self.reservoirInfo.items():
            name, cofactor, redox_state, num_electron, deltaG, rate = info
            cof_id = self.cofactor2id[cofactor]
            self.connectReservoirRate(cof_id, redox_state, redox_state - num_electron, rate, deltaG)

    def ET(self, deltaG: float, R: float, reorgE, beta, V, vibfreq=0.15, quanta=100, D=0.5) -> float:
        """
        Calculate the nonadiabatic ET rate according to Marcus theory with vibrational states
        Arguments:
            deltaG {float} -- Reaction free energy, unit: eV
            R {float} -- Distance for decay factor, unit: angstrom
            reorgE {float} -- Reorganization energy, unit: eV
            beta {float} -- Inverse of kT, unit: 1/eV
            V {float} -- Electronic coupling, unit: eV
            vibfreq {float} -- Vibrational frequency, unit: eV
            quanta {int} -- Number of vibrational quanta
            D {float} -- Huang-Rhys factor
        Returns:
            float -- Nonadiabatic ET rate, unit: 1/s
        """
        k_total = 0
        for n in range(quanta + 1):
            modified_deltaG = deltaG + n * vibfreq
            Franck_Condon_factor = np.exp(-D) * D**n / math.factorial(n)
            k_n = (2 * math.pi / self.hbar) * (V * np.exp(-0.6 * R))**2 * (1 / math.sqrt(4 * math.pi * (1 / beta)
                                                                                         * reorgE)) * np.exp(-beta * (modified_deltaG + reorgE)**2 / (4 * reorgE)) * Franck_Condon_factor
            k_total += k_n

        return k_total

    def connectStateRate(self, cof_i: int, red_i: int, cof_f: int, red_f: int, dis: float, reorgE: float, num_electrons: int):
        """
        Add rate constant k between electron donor (cof_i) and acceptor (cof_f) with initial redox state and final redox state stated (red_i, red_f)
        ADDITION: this function combine with detailed balancing feature, helps to save initialization time.
        Arguments:
            cof_i {int} -- Donor cofactor ID
            red_i {int} -- Redox state for donor ID
            cof_f {int} -- Acceptor cofactor ID
            red_f {int} -- Redox state for acceptor ID
            k {float} -- forward state
            deltaG {float} -- deltaG between initial state and final state
        """
        for i in range(self.adj_num_state):
            # loop through all allowed states, to look for initial (donor) state
            if self.idx2state(self.allow[i])[cof_i] == red_i and self.idx2state(self.allow[i])[cof_f] == red_f:
                """
                ex. idx:some (allowed) number -> state:[0 1 1 0 2 3 ...]
                    idx2state(allow[i])[cof_i] -> ith element of the state:[0 1 1 0 2 3...]
                Basically, this "if" statement means: 
                "If cof_ith element of the state:[0 1 1 0 2 3...] is equal to the redox state of the cof_i" and also 
                "If cof_fth element of the state:[0 1 1 0 2 3...] is equal to the redox state of the cof_f"
                """

                for j in range(self.adj_num_state):
                    # loop through all allowed states, to look for final (acceptor) state
                    if self.idx2state(self.allow[j])[cof_i] == red_i - num_electrons and self.idx2state(self.allow[j])[cof_f] == red_f + num_electrons:
                        """
                        ex. idx:some allowed number -> state:[0 1 1 0 2 3 ...]
                            idx2state(allow[i])[cof_i] -> ith element of the state:[0 1 1 0 2 3...]
                        Basically, this "if" statement means: 
                        "If cof_ith element of the state:[0 1 1 0 2 3...] is equal to the (redox state - 1) (donates electron so this cofactor is oxidized) of the cof_i" and also 
                        "If cof_fth element of the state:[0 1 1 0 2 3...] is equal to the (redox state + 1) (accepts electron so this cofactor is reduced) of the cof_f"
                           """
                        # initial, final state found! check other electron conservation
                        # Do not allow changes other than cof_i and cof_f we have searched for
                        I = np.delete(self.idx2state(
                            self.allow[i]), [cof_i, cof_f])
                        # Deleting the cof_i and cof_f that is already checked to be correct
                        J = np.delete(self.idx2state(
                            self.allow[j]), [cof_i, cof_f])
                        # Checking that sites other than cof_i and cof_f hasn't changed
                        if np.array_equal(I, J):
                            # i and j state found!
                            state_i = self.idx2state(self.allow[i])
                            state_j = self.idx2state(self.allow[j])
                            deltaG = self.deltaG_coulomb_calculation(state_i, state_j, cof_i, cof_f, red_i, red_f)
                            k = self.ET(deltaG, dis, reorgE, self.beta, self.V)
                            kf = k  # forward rate
                            kb = k * np.exp(self.beta*deltaG)
                            # add population of final state, forward process
                            self.K[j][i] += kf
                            # remove population of initial state, forward process   #Diagonal elements are the negative sum of the other elements in the same column
                            self.K[i][i] -= kf
                            # add population of initial state, backward process
                            self.K[i][j] += kb
                            # remove population of final sate, backward process
                            self.K[j][j] -= kb
    def deltaG_coulomb_calculation(self, state_i, state_j, cof_i, cof_f, red_i, red_f):
        sum_eps_i = 0
        sum_eps_j = 0
        # for i, index in zip(state_i, range(len(state_i))):
        #     if index != cof_i and i > 0: 
        #         dis = self.D[cof_i][index]
        #         # print("dist: ", dis, cof_i, index)
        #         eps = 14.39 / self.eps_r / dis * i * state_i[cof_i]
        #         # print("eps: ", eps)
        #         sum_eps_i += eps
        # for j, index in zip(state_j, range(len(state_j))):
        #     if index != cof_f and j > 0: 
        #         dis = self.D[cof_f][index]
        #         # print("dist: ", dis, cof_f, index)
        #         eps = 14.39 / self.eps_r / dis * j * state_j[cof_f]
        #         # print("eps: ", eps)
        #         sum_eps_j += eps
        # # print("sum i: ", sum_eps_i)
        # # print("sum_j: ", sum_eps_j)
        cof_i = self.id2cofactor[cof_i]
        # # Finding the name of cofactor of the ijth of the adjacency matrix
        cof_f = self.id2cofactor[cof_f]
        # deltaG = cof_i.redox[red_i - 1] - sum_eps_i - cof_f.redox[red_f] + sum_eps_j
        
        
        energy_state_i = 0
        energy_state_j = 0
        for i, index in zip(state_i, range(len(state_i))):
            energy_state_i -= i * self.id2cofactor[index].redox[i-1]
        for j, index in zip(state_j, range(len(state_j))):
            energy_state_j -= j * self.id2cofactor[index].redox[j-1]
        
        for i, index in zip(state_i, range(len(state_i))):
            for j, other_index in zip(state_i, range(len(state_i))):
                if index != other_index and i > 0 and j > 0:
                    dis = self.D[index][other_index]
                    eps = 14.39 / self.eps_r / dis * i * j
                    sum_eps_i += eps
        for i, index in zip(state_j, range(len(state_j))):
            for j, other_index in zip(state_j, range(len(state_j))):
                if index != other_index and i > 0 and j > 0:
                    dis = self.D[index][other_index]
                    eps = 14.39 / self.eps_r / dis * i * j
                    sum_eps_j += eps
        
        deltaG = energy_state_j + sum_eps_j - energy_state_i - sum_eps_i
        # print("state_i: ", state_i)
        # print("state_j: ", state_j)
        # print("With coulomb: ", deltaG)
        # print("Without coulomb: ",
        #     cof_i.redox[red_i - 1] - cof_f.redox[red_f])
        # print("antother way to calculate without coulomb: ", energy_state_j - energy_state_i)
        # print("energy state i: ", energy_state_i)
        # print("energy state j: ", energy_state_j)
        # print("sum eps i: ", sum_eps_i)
        # print("sum eps j: ", sum_eps_j)
        
        return deltaG


    def connectReservoirRate(self, cof_id: int, red_i: int, red_f: int, k: float, deltaG: float):
        """
        Add rate constant k between red_i and red_f of a cofactor, which is connected to a reservoir
        ADDITION: this function combine with detailed balancing feature, helps to save initialization time.
        Arguments:
            cof_id {int} -- Cofactor ID
            red_i {int} -- Redox state for cofactor
            red_f {int} -- Redox state for cofactor
            k {float} -- forward state
            deltaG {float} -- deltaG between initial state and final state
        """
        # if self.max_electrons == None:
        self.max_electrons = sum([site for site in self.siteCapacity])
        for i in range(self.adj_num_state):
            # loop through all allowed states, to look for initial (donor) state
            # if sum(self.idx2state(self.allow[i])) <= self.max_electrons:
            if self.idx2state(self.allow[i])[cof_id] == red_i:
                """
                    ex. idx:some number -> state:[0 1 1 0 2 3 ...]
                    idx2state(i)[cof_i] -> ith element of the state:[0 1 1 0 2 3...]
                    Basically, this "if" statement means:
                    "If cof th element of the state:[0 1 1 0 2 3...] is equal to the redox state of the cofactor"
                    """
                for j in range(self.adj_num_state):
                    # loop through all allowed states, to look for final (acceptor) state
                    if self.idx2state(self.allow[j])[cof_id] == red_f:
                        """
                            ex. idx:some number -> state:[0 1 1 0 2 3 ...]
                            idx2state(i)[cof_i] -> ith element of the state:[0 1 1 0 2 3...]
                            Basically, this "if" statement means: 
                            "If cof th element of the state:[0 1 1 0 2 3...] is equal to the redox state of the final cofactor"
                            """
                        # initial, final state found! check other electron conservation
                        I = np.delete(self.idx2state(
                            self.allow[i]), [cof_id])
                        J = np.delete(self.idx2state(
                            self.allow[j]), [cof_id])
                        if np.array_equal(I, J):
                            # i and j state found!
                            kf = k  # forward rate
                            kb = k * np.exp(self.beta*deltaG)
                            # add population of final state, forward process
                            self.K[j][i] += kf
                            # remove population of initial state, forward process
                            self.K[i][i] -= kf
                            # add population of initial state, backward process
                            self.K[i][j] += kb
                            # remove population of final state, backward process
                            self.K[j][j] -= kb

    def addMultiElectronConnection(self, cof_i, cof_f, donor_state: int, acceptor_state: int, num_electrons, k):
        i = self.cofactor2id[cof_i]
        # Finding the name of cofactor of the ijth of the adjacency matrix
        f = self.cofactor2id[cof_f]
        deltaG = sum([cof_i.redox[donor_state-num_electrons + n] -
                     cof_f.redox[acceptor_state+n] for n in range(0, num_electrons)])
        # Adding the rate constant to rate matrix
        self.connectStateRate(
            i, donor_state, f, acceptor_state, k, deltaG, num_electrons)

    def getNonConservedStates(self, num_electrons: int) -> list:
        """
        When you build a closed system with conserved number of electrons, this function finds which state breaks the conservation
        Arguments:
            num_electrons {int}  -- Total number of electrons in a closed system
        Returns:
            list -- list of states whose total number of electrons is not equal to num_electron
        """
        ncstates = []
        for i in range(self.num_state):  # loop through all the possible states
            # print(net.idx2state(i))   #printing out all the possible states
            sum = 0
            for j in range(self.num_cofactor):
                # sum the numbers included in the state list to get the total number of electrons in that state
                sum += self.idx2state(i)[j]
            # print(sum)
            if sum != num_electrons:
                # States whose total number of electrons is not equal to num_electron
                nc = self.idx2state(i)
            ncstates.append(nc)
        # print(ncstates)
        return ncstates  # List of states whose total number of electrons is not equal to num_electron

    def constructRateMatrix_old(self, reorgE=0.2):
        """
        Build rate matrix
        """
        # initialize the rate matrix with proper dimension
        # The dimension of the rate matrix is basically equal to the total number of states
        self.K = np.zeros(
            (self.adj_num_state, self.adj_num_state), dtype=float)
        # loop through cofactor_id in adjacency matrix
        """
        Take the adjacency matrix which is weighted by the distance to construct the full rate matrix
        """
        for i in range(self.num_cofactor):
            # These two "for" loops take care of (upper triangular - diagonal) part of the adjacency matrix
            for j in range(i+1, self.num_cofactor):
                if self.D[i][j] != 0:  # cofactor i and j are connected!  !=:not equal to
                    cof_i = self.id2cofactor[i]
                    # Finding the name of cofactor of the ijth of the adjacency matrix
                    cof_f = self.id2cofactor[j]
                    # Distance between cof_i and cof_f is the ij th element of the adjacency matrix
                    dis = self.D[i][j]
                    """
                    Looping through all the possible transfers from donor to acceptor to find their reduction potentials to get deltaG of that transfer. 
                    You use that deltaG to get the Marcus rate of that transfer, and then add that rate constant to the rate matrix.
                    """
                    for donor_state in range(1, cof_i.capacity+1):  # This is correct!!!! Python is weird      #cof.capacity=maximum number of electrons the cofactor can occupy
                        # This is correct!!!! Python is weird
                        for acceptor_state in range(0, cof_f.capacity):
                            # This is correct!!!! Python is weird
                            deltaG = cof_i.redox[donor_state -
                                                 1] - cof_f.redox[acceptor_state]
                            k = self.ET(deltaG, dis, reorgE, self.beta, self.V)
                            # Adding the rate constant to rate matrix. The last parameter is 1 because these are all 1-electron transfers!
                            self.connectStateRate(
                                i, donor_state, j, acceptor_state, k, deltaG, 1)
        # loop through reservoirInfo to add reservoir-related rate
        for reservoir_id, info in self.reservoirInfo.items():
            name, cofactor, redox_state, num_electron, deltaG, rate = info
            cof_id = self.cofactor2id[cofactor]
            final_redox_state = redox_state - num_electron
            self.connectReservoirRate(
                cof_id, redox_state, final_redox_state, rate, deltaG)
            # Define the epsilon calculation function here

    def constructRateMatrix(self, reorgE=0.2):
        self.K = np.zeros(
            (self.adj_num_state, self.adj_num_state), dtype=float)
        # loop through cofactor_id in adjacency matrix
        """
        Take the adjacency matrix which is weighted by the distance to construct the full rate matrix
        """
        for i in range(self.num_cofactor):
            # These two "for" loops take care of (upper triangular - diagonal) part of the adjacency matrix
            for j in range(i+1, self.num_cofactor):
                if self.D[i][j] != 0:  # cofactor i and j are connected!  !=:not equal to
                    cof_i = self.id2cofactor[i]
                    # Finding the name of cofactor of the ijth of the adjacency matrix
                    cof_f = self.id2cofactor[j]
                    # Distance between cof_i and cof_f is the ij th element of the adjacency matrix
                    dis = self.D[i][j]
                    """
                    Looping through all the possible transfers from donor to acceptor to find their reduction potentials to get deltaG of that transfer. 
                    You use that deltaG to get the Marcus rate of that transfer, and then add that rate constant to the rate matrix.
                    """
                    for donor_state in range(1, cof_i.capacity+1):  # This is correct!!!! Python is weird      #cof.capacity=maximum number of electrons the cofactor can occupy
                        # This is correct!!!! Python is weird
                        for acceptor_state in range(0, cof_f.capacity):
                            # This is correct!!!! Python is weird

                            # Adding the rate constant to rate matrix. The last parameter is 1 because these are all 1-electron transfers!
                            self.connectStateRate(
                                i, donor_state, j, acceptor_state, dis, reorgE, 1)
        # loop through reservoirInfo to add reservoir-related rate
        for reservoir_id, info in self.reservoirInfo.items():
            name, cofactor, redox_state, num_electron, deltaG, rate = info
            cof_id = self.cofactor2id[cofactor]
            final_redox_state = redox_state - num_electron
            self.connectReservoirRate(
                cof_id, redox_state, final_redox_state, rate, deltaG)
            
        
        
    def simple_propensity(self, rateconstants, population, t, x: int):
        #     Updates an array of propensities given a set of parameters
        #     and an array of populations

        # Unpack population
        pop = population

        # Update propensities
        for i in range(self.adj_num_state):
            # x is the constant: this is where the microstate is!!
            rateconstants[i] = self.K[i][x]
            # x changes over timestep because population changes and which transition happens depends on where the microstate is and the random number

    def sample_discrete(self, probs, x):  # Align probability and give a random number
        # Randomly sample an index with probability given by probs

        # Generate random number
        q = np.random.rand()

        # Find index     #Find next microstate
        i = 0
        p_sum = 0.0
        for i in range(self.adj_num_state):
            if x != i:
                p_sum += probs[i]
            if p_sum >= q:
                break

        return i

    def simple_update(self):
        updatearray = np.identity(self.adj_num_state, dtype=float)
        return updatearray

    # rateconstant/sum of column elements
    def gillespie_draw(self, propensity_func, rateconstants, population, t, x):
        #     Draws a reaction and the time it took to do that reaction.

        #     Parameters
        #     ----------
        #     propensity_func : function
        #         Function with call signature propensity_func(population, t, *args)
        #         used for computing propensities. This function must return
        #         an array of propensities.
        #     population : ndarray
        #         Current population of particles
        #     t : float
        #         Value of the current time.
        #     args : tuple, default ()
        #         Arguments to be passed to `propensity_func`.

        #     Returns
        #     -------
        #     rxn : int
        #         Index of reaction that occured.
        #     time : float
        #         Time it took for the reaction to occur.

        # Compute propensities
        propensity_func(rateconstants, population, t, x)
        # print(rateconstants)
        # Sum of propensities
        gamma = 0
        for i in range(len(rateconstants)):
            if x != i:
                gamma += rateconstants[i]
        # print(gamma)
        # Find next time interval
        time = np.random.exponential(1.0 / gamma)
        # Compute discrete probabilities of each reaction
        # props_sum is the gamma(=sum of rate constants)
        rxn_probs = rateconstants / gamma
        # print(rxn_probs)
        # Draw reaction from this distribution
        rxn = self.sample_discrete(rxn_probs, x)
        # print(rxn)
        # print(time)

        return rxn, time

    def gillespie_ssa(self, propensity_func, update, population_0, time_points, x):
        #     Uses the Gillespie stochastic simulation algorithm to sample
        #     from probability distribution of particle counts over time.

        #     Parameters
        #     ----------
        #     propensity_func : function
        #         Function of the form f(params, t, population) that takes the current
        #         population of particle counts and return an array of propensities
        #         for each reaction.
        #     update : ndarray, shape (num_reactions, num_chemical_species)
        #         Entry i, j gives the change in particle counts of species j
        #         for chemical reaction i.
        #     population_0 : array_like, shape (num_chemical_species)
        #         Array of initial populations of all chemical species.
        #     time_points : array_like, shape (num_time_points,)
        #         Array of points in time for which to sample the probability
        #         distribution.
        #     args : tuple, default ()
        #         The set of parameters to be passed to propensity_func.

        #     Returns
        #     -------
        #     sample : ndarray, shape (num_time_points, num_chemical_species)
        #         Entry i, j is the count of chemical species j at time
        #         time_points[i].

        # Initialize output
        pop_out = np.empty(
            (len(time_points), self.adj_num_state), dtype=np.int)

    # Initialize and perform simulation
        i_time = 1
        i = 0
        t = time_points[0]
        population = population_0.copy()
        pop_out[0, :] = population
        rateconstants = np.zeros(self.adj_num_state)
        while i < len(time_points):
            # The timestep defined by time_points (in this case 0.2 s) do not proceed unless the sum of dt's does not reach the timestep.
            while t < time_points[i_time]:
                # draw the event and time step
                # event: state that it jumps to,    dt: time interval
                event, dt = self.gillespie_draw(
                    propensity_func, rateconstants, population, t, x)
                x = event  # new x depend on event and this x needs to be iterated into the next Gillespie loop
            # Update the population
                population_previous = population.copy()
                # state a -> state b transition in time interval dt. In this time interval, pop of state a: 1->0 and pop of state_b: 0 -> 1
                population += update[:, event]
                # If population = update[:,event], we can see transitions per time interval (like instantaneous transition in a time interval t)
                # If population = update[:,event], we can see transitions per time interval (like average transition in a time interval t)
            # Increment time
                t += dt
        # Update the index
            i = np.searchsorted(time_points > t, True)
        # Update the population
            pop_out[i_time:min(i, len(time_points))] = population_previous
        # Increment index
            i_time = i

        return pop_out  # pop_out: population of each state

    def listConnectedStates(self) -> list:
        """
        List the states that are connected
        Returns:
            list -- [i (row number of K), j (column number of K), [ith state], [jth state]]
        """
        # search for rate matrix elements that are nonzero -> search for states that are connected
        connectedstates = []
        for i in range(self.adj_num_state):  # loop through all the possible states
            for j in range(self.adj_num_state):  # looks through all the possible states
                if (self.K[i][j] != 0):
                    connectedstates.append([i, j, self.idx2state(self.allow[i]), self.idx2state(
                        self.allow[j]), self.K[i][j]])  # list up states that are connected

        return connectedstates

    def checkConnectedStates(self, num_electrons: int) -> list:
        """
        List the states that are connected (limited to states that have conserved number of electrons)
        Arguments:
            num_electrons {int}  -- Total number of electrons in a closed system
        Returns:
            list -- [i (row number of K), j (column number of K), [ith state], [jth state]]
        """
        # search for rate matrix elements that are nonzero -> search for states that are connected
        numelectrons = self.totalnumelectron()
        connectedstates = []
        for i in range(self.adj_num_state):  # loop through all the possible states
            # looks through upper triangular part -> not including the diagonal elements and reverse transition
            for j in range(i+1, self.adj_num_state):
                if (self.K[i][j] != 0) and (numelectrons[i] == num_electrons):
                    connectedstates.append([i, j, self.idx2state(self.allow[i]), self.idx2state(
                        self.allow[j]), self.K[i][j]])  # list up states that are connected

        return connectedstates

    def totalnumelectron(self) -> list:
        """
        Calculate the total number of particles in the system.
        Returns:
            list of total number of particles in all the possible states
        """
        numelectrons = []
        for i in range(self.adj_num_state):  # loop through all the possible states
            # print(self.idx2state(i))   #printing out all the possible states
            sum = 0
            for j in range(self.num_cofactor):
                # sum the numbers included in the state list to get the total number of electrons in that state
                sum += self.idx2state(self.allow[i])[j]
            numelectrons.append(sum)
            # print(self.idx2state(i), sum)

        return numelectrons

    def listAllStates(self):
        """
        List up all the possible states of the model
        """
        allstates = []
        for i in range(self.adj_num_state):
            # list: allstates=[state, ith]
            allstates.append([self.idx2state(self.allow[i]), i])
        # print(len(allstates))     #len(allstates)=self.num_states
        print(allstates)
        return allstates

    ########################################
    ####    Data Analysis Functions     ####
    ########################################

    def population(self, pop: np.array, cofactor: Cofactor, redox: int) -> float:
        """
        Calculate the population of a cofactor in a given redox state
         -> (ex.)pop=[1 0 0 2 5 ...]:len(pop)=num_state, pop is the population vector of the states. (pop[0]=population of state[0], pop[1]=population of state[1]...)

        Arguments:
            pop {numpy.array} -- Population vector     This is the population vector of the states. len(pop)=self.adj_num_state
            cofactor {Cofactor} -- Cofactor object
            redox {int} -- Redox state of the cofactor
        Returns:
            float -- Population of the cofactor at specific redox state
        """
        cof_id = self.cofactor2id[cofactor]
        ans = 0
        for i in range(len(pop)):
            # Loop through all the possible states
            # For every state, the number of electrons on each site is known, (ex.)state[0]=[1 2 0 3 2...], state[1]=[0 2 3 1 ...]
            if self.idx2state(self.allow[i])[cof_id] == redox:
                # It loops through all the states to find where the cof th element of (ex.)state:[0 1 1 0 2 3...] is equal to the given redox state
                # Population of electron at each cofactor = redox state of that cofactor
                ans += pop[i]

        return ans

    def gillespie_pop2hopping_pop(self, gillespie_pop, t):
        """
        Probability of the states over at a given time
        Choosing time is choosing the row of gillespie_pop. This is the parameter "t"
        """
        sum = 0
        for i in range(self.adj_num_state):
            # one of the rows in gillespie's pop_out
            sum += gillespie_pop[t][i]

        hopping_pop = []
        for i in range(self.adj_num_state):
            hopping_pop.append(gillespie_pop[t][i]/sum)

        return hopping_pop

    def getCofactorRate(self, cof_i: Cofactor, red_i: int, cof_f: Cofactor, red_f: int, pop: np.array) -> float:
        """
        Calculate the instantaneous forward rate from cof_i to cof_f
        Arguments:
            cof_i {Cofactor} -- Cofactor object for initial cofactor
            red_i {int} -- Redox state for initial cofactor
            cof_f {Cofactor} -- Cofactor object for final cofactor
            red_f {int} -- Redox state for final cofactor
            pop {np.array} -- Population vector      This is the population vector of the states. len(pop)=self.num_state
        Returns:
            float -- Instantaneous forward rate
        """
        cof_i_id = self.cofactor2id[cof_i]
        cof_f_id = self.cofactor2id[cof_f]
        flux = 0
        for i in range(self.adj_num_state):
            # loop through all states, to find initial state
            if self.idx2state(self.allow[i])[cof_i_id] == red_i and self.idx2state(self.allow[i])[cof_f_id] == red_f - 1:
                """
                This "if" statement means: 
                "If the element that corresponds to cof_i in the state:[0 1 1 0 2 3...] is equal to the redox state of cof_i (prior to donating an electron)" and
                "If the element that corresponds to cof_f in the state:[0 1 1 0 2 3...] is equal to the (redox state of cof_f -1) (prior to accepting an electron)"
                """
                for j in range(self.adj_num_state):
                    # loop through all states, to find final state
                    if self.idx2state(self.allow[j])[cof_i_id] == red_i - 1 and self.idx2state(self.allow[j])[cof_f_id] == red_f:
                        """
                        This "if" statement means: 
                        "If the element that corresponds to cof_i in the state:[0 1 1 0 2 3...] is equal to the (redox state of cof_i -1) (donated an electron)" and
                        "If the element that corresponds to cof_f in the state:[0 1 1 0 2 3...] is equal to the redox state of cof_f (accepted an electron)"
                        """
                        # initial, final state found! check other electron conservation
                        I = np.delete(self.idx2state(
                            self.allow[i]), [cof_i_id, cof_f_id])
                        J = np.delete(self.idx2state(
                            self.allow[j]), [cof_i_id, cof_f_id])
                        if np.array_equal(I, J):
                            # i and j state found!)
                            # K is rate matrix, so len(K)=self.num_state
                            flux += self.K[j][i] * pop[i]

        return flux

    def getCofactorFlux(self, cof_i: Cofactor, red_i: int, cof_f: Cofactor, red_f: int, pop: np.array) -> float:
        """
        Calculate the instantaneous NET flux from initial cofactor(state) to final cofactor(state), by calling getCofactorRate() twice
        Arguments:
            cof_i {Cofactor} -- Cofactor object for initial cofactor
            red_i {int} -- Redox state for initial cofactor before ET
            cof_f {Cofactor} -- Cofactor object for final cofactor
            red_f {int} -- Redox state for final cofactor after ET
            pop {np.array} -- Population vector      This is the population vector of the states. len(pop)=self.num_state
        Returns:
            float -- Instantaneous net flux
        """
        return self.getCofactorRate(cof_i, red_i, cof_f, red_f, pop) - self.getCofactorRate(cof_f, red_f, cof_i, red_i, pop)

    def getReservoirFlux(self, name: str, pop: np.array) -> float:
        """
        Calculate the instantaneous net flux into the reservoir connected to the reservoir
        Arguments:
            reservoir_id {int} -- Reservoir ID
            pop {np.array} -- Population vector      This is the population vector of the states. len(pop)=self.num_state
        Returns:
            float -- Instantaneous net flux connected to the reservoir
        """
        reservoir_id = self.reservoir2id[name]
        name, cofactor, redox_state, num_electron, deltaG, rate = self.reservoirInfo[
            reservoir_id]
        reverse_rate = rate * np.exp(self.beta*deltaG)
        # redox_state is basically the initial redox state of the cofactor, which is info stored in reservoirInfo dict()
        final_redox = redox_state-num_electron

        return (self.population(pop, cofactor, redox_state) * rate - self.population(pop, cofactor, final_redox) * reverse_rate) * num_electron

    def reservoirFluxPlot(self, pop_init: np.array, t: float) -> list:
        """
        Calculate the net flux into a reservoir given its id versus time
        Arguments:
            t {float} -- Final time
            pop_init {np.array} -- Initial population vector (default: None)
            reservoir_id {int} -- Reservoir id
        Returns:
            list -- Net flux into the reservoir along a period of time
        """
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        res_list = []  # list of reservoir names
        for reservoir_id in range(self.num_reservoir):
            name, cofactor, redox_state, num_electron, deltaG, rate = self.reservoirInfo[
                reservoir_id]
            res_list.append(name)
        # print(res_list)
        for res in res_list:
            T = np.linspace(0, t, 1000)  # default spacing number: 1000
            fluxes = []
            for time in T:
                pop = self.evolve(time, pop_init)
                flux = self.getReservoirFlux(res, pop)
                fluxes.append(flux)
            # print(fluxes)
            plt.plot(T, fluxes, label=res)

        plt.legend(loc="upper right")
        ax.set_xlabel('time (sec)', size='x-large')
        ax.set_ylabel('Flux', size='x-large')

    def popPlot(self, cof_list, pop_init: np.array, t: float) -> list:
        """
        Calculate the population of a given cofactor at specific redox state along a period of time
        Arguments:
            t {float} -- Final time
            pop_init {numpy.array} -- Initial population vector (default: None)
            cof_list {array} -- a list containing lists [cof, redox] where cof is a cofactor whose population is to be plotted, and redox is the desired redox state to be plotted
        Returns:
            list -- Population of the cofactor along a period of time
        """
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        for cof in cof_list:
            T = np.linspace(0, t, 100)  # default spacing number: 100
            A = []
            pops = []  # population at site i
            for time in T:
                pop = self.evolve(time, pop_init)
                A.append(pop)
                pops.append(self.population(A[-1], cof[0], cof[1]))

            plt.plot(T, pops, label=cof[0].name +
                     " (redox state = " + str(cof[1]) + ")")

        plt.legend(loc="upper right")
        ax.set_xlabel('time (sec)', size='x-large')
        ax.set_ylabel('Probability', size='x-large')
        plt.show()

    def getExptvalue(self, pop: np.array, cofactor: Cofactor) -> float:
        """
        Calculate the expectation value of the number of particles at a given cofactor at a given time
        Arguments:
            cofactor {Cofactor} -- Cofactor object
            pop {cp.array} -- Population vector of the states
        """
        cof_id = self.cofactor2id[cofactor]
        expt = 0
        # loop through all the possible states
        for i in range(self.adj_num_state):
            # sum((number of particle)*(probability))
            expt += self.idx2state(self.allow[i])[cof_id]*pop[i]

        return expt

    def popState(self, pop_init: np.array, t: float) -> list:
        """
        Visualize the population of the microstates at a given time
        Arguments:
            t {float} -- given time
            pop_init {numpy.array} -- Initial population vector (default: None)
        Returns:
            list -- [[population, microstate that corresponds to that population]]
        """
        popstate = []
        pop = self.evolve(t, pop_init)
        for i in range(self.adj_num_state):
            popstate.append([pop[i], self.idx2state(self.allow[i])])

        return popstate

    def getJointExptvalue(self, pop: np.array, cofactor_1: Cofactor, red_1: int, cofactor_2: Cofactor, red_2: int) -> float:
        """
        Calculate the joint probability of cofactor_1 being in redox state (red_1) and cofactor_2 being in redox state (red_2)
        Arguments:
            cofactor {Cofactor} -- Cofactor object
            pop {cp.array} -- Population vector of the states
        """
        cof1_id = self.cofactor2id[cofactor_1]
        cof2_id = self.cofactor2id[cofactor_2]
        expt = 0
        for i in range(self.adj_num_state):
            if self.idx2state(self.allow[i])[cof1_id] == red_1 and self.idx2state(self.allow[i])[cof2_id] == red_2:
                expt += pop[i]
        return expt
