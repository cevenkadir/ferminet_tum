import jax
import chex
from typing import Sequence
from functools import partial


@chex.dataclass
class NetParams:
    """Network parameters class for the FermiNet.

    Args:
        V (`Sequence[chex.ArrayDevice]`): The weights for one-electron linear layers.
        b (`Sequence[chex.ArrayDevice]`): The biases for one-electron linear layers.
        W (`Sequence[chex.ArrayDevice]`): The weights for two-electron linear layers.
        c (`Sequence[chex.ArrayDevice]`): The biases for two-electron linear layers.
        w_alpha (`chex.ArrayDevice`): The weights for the final layer.
        g_alpha (`chex.ArrayDevice`): The biases for the final layer.
        Sigma_alpha (`chex.ArrayDevice`): The envelope decays.
        pi_alpha (`chex.ArrayDevice`): The envelope weights.
        omega (`chex.ArrayDevice`): The weights in determinant expansion.
    """

    _V: Sequence[chex.ArrayDevice]
    _b: Sequence[chex.ArrayDevice]
    _W: Sequence[chex.ArrayDevice]
    _c: Sequence[chex.ArrayDevice]
    _w_alpha: chex.ArrayDevice
    _g_alpha: chex.ArrayDevice
    _Sigma_alpha: chex.ArrayDevice
    _pi_alpha: chex.ArrayDevice
    _omega: chex.ArrayDevice

    @classmethod
    def init(
        cls,
        n_1: Sequence[int],
        n_2: Sequence[int],
        n_k: int,
        n_electrons: Sequence[int],
        n_atoms: int,
        seed=jax.random.PRNGKey(0),
    ):
        """Initializes and returns a NetParams instance for the given parameters.

        Args:
            n_1 (`Sequence[int]`): The numbers of hidden units for the one-eleectron stream.
            n_2 (`Sequence[int]`): The numbers of hidden units for the two-electron stream.
            n_k (`int`): The number of many-electron determinants.
            n_electrons (`Sequence[int]`): The number of alpha and beta electrons.
            n_atoms (`int`): The total number of atoms.
            seed (optional): The random seed. Defaults to jax.random.PRNGKey(0).

        Returns:
            `ferminet_tum.params.NetParams`: The initialized NetParams object for the given parameters.
        """

        # choose the Xavier uniform initialization as the default for the weights and biases
        init_func = partial(
            jax.nn.initializers.glorot_normal, in_axis=-1, out_axis=-2
        )()

        # choose the standard normal initialization as the default for the others
        init_func_for_vectors = jax.random.normal

        # get the number of layers
        n_layer = len(n_1)

        # get the total number of electrons
        n_total_electrons = sum(n_electrons)

        over_factor = 1 / 1

        V = [
            init_func(seed, shape=(n_1[i], 3 * n_1[i - 1] + 2 * n_2[i - 1]))
            * over_factor
            if i != 0
            else init_func(seed, shape=(n_1[i], 3 * 4 * n_atoms + 2 * 4)) * over_factor
            for i in range(n_layer)
        ]

        b = [
            init_func_for_vectors(seed, shape=(n_1[i],)) * over_factor
            for i in range(n_layer)
        ]

        W = [
            init_func(seed, shape=(n_2[i], n_2[i - 1])) * over_factor
            if i != 0
            else init_func(seed, shape=(n_2[i], 4)) * over_factor
            for i in range(n_layer)
        ]
        c = [
            init_func_for_vectors(seed, shape=(n_2[i],)) * over_factor
            for i in range(n_layer)
        ]

        w_alpha = (
            init_func_for_vectors(seed, shape=(n_k, n_total_electrons, n_1[-1]))
            * over_factor
        )

        g_alpha = (
            init_func_for_vectors(seed, shape=(n_k, n_total_electrons)) * over_factor
        )

        Sigma_alpha = (
            init_func_for_vectors(seed, shape=(n_k, n_total_electrons, n_atoms, 3, 3))
            * over_factor
        )

        pi_alpha = (
            init_func_for_vectors(seed, shape=(n_k, n_total_electrons, n_atoms))
            * over_factor
        )

        omega = init_func_for_vectors(seed, shape=(n_k,)) * over_factor

        return cls(
            _V=V,
            _b=b,
            _W=W,
            _c=c,
            _w_alpha=w_alpha,
            _g_alpha=g_alpha,
            _Sigma_alpha=Sigma_alpha,
            _pi_alpha=pi_alpha,
            _omega=omega,
        )

    @property
    def total_n_parameters(self) -> int:
        """`int`: The total number of parameters in the network."""
        n_parameters = 0

        n_parameters += sum(V_i.size for V_i in self.V)
        n_parameters += sum(b_i.size for b_i in self.b)
        n_parameters += sum(W_i.size for W_i in self.W)
        n_parameters += sum(c_i.size for c_i in self.c)

        n_parameters += self.w_alpha.size
        n_parameters += self.g_alpha.size
        n_parameters += self.Sigma_alpha.size
        n_parameters += self.pi_alpha.size
        n_parameters += self.omega.size

        return n_parameters

    @property
    def V(self) -> Sequence[chex.ArrayDevice]:
        """`Sequence[chex.ArrayDevice]`: The weights for one-electron linear layers."""
        return self._V

    @property
    def b(self) -> Sequence[chex.ArrayDevice]:
        """`Sequence[chex.ArrayDevice]`: The biases for one-electron linear layers."""
        return self._b

    @property
    def W(self) -> Sequence[chex.ArrayDevice]:
        """`Sequence[chex.ArrayDevice]`: The weights for two-electron linear layers."""
        return self._W

    @property
    def c(self) -> Sequence[chex.ArrayDevice]:
        """`Sequence[chex.ArrayDevice]`: The biases for two-electron linear layers."""
        return self._c

    @property
    def w_alpha(self) -> chex.ArrayDevice:
        """`chex.ArrayDevice`: The weights for the final layer."""
        return self._w_alpha

    @property
    def g_alpha(self) -> chex.ArrayDevice:
        """`chex.ArrayDevice`: The biases for the final layer."""
        return self._g_alpha

    @property
    def Sigma_alpha(self) -> chex.ArrayDevice:
        """`chex.ArrayDevice`: The envelope decays."""
        return self._Sigma_alpha

    @property
    def pi_alpha(self) -> chex.ArrayDevice:
        """`chex.ArrayDevice`: The envelope weights."""
        return self._pi_alpha

    @property
    def omega(self) -> chex.ArrayDevice:
        """`chex.ArrayDevice`: The weights in determinant expansion."""
        return self._omega
