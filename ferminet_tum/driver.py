import jax.numpy as jnp
import numpy as np
import jax
import optax
from typing import Sequence, Union
from tqdm.auto import tqdm
import h5py

from .sampler import Sampler
from .hamiltonian import Hamiltonian
from .network import FermiNet
from .params import NetParams


class NNQS:
    def __init__(
        self,
        sampler: Sampler,
        hamiltonian: Hamiltonian,
        ferminet: FermiNet,
        batch_size: int = 4096,
    ):
        self._sampler = sampler
        self._hamiltonian = hamiltonian
        self._ferminet = ferminet

        self._batch_size = batch_size

    @property
    def sampler(self) -> Sampler:
        """(`Sampler`): The sampler instance."""
        return self._sampler

    @property
    def hamiltonian(self) -> Hamiltonian:
        """(`Hamiltonian`): The Hamiltonian instance."""
        return self._hamiltonian

    @property
    def ferminet(self) -> FermiNet:
        """(`FermiNet`): The FermiNet instance."""
        return self._ferminet

    @property
    def batch_size(self) -> int:
        """(`int`): The batch size."""
        return self._batch_size

    def calc_local_energy_kernel(
        self,
        carry: tuple,
        x,
    ) -> Union[tuple, jnp.DeviceArray,]:
        """Define the kernel for calculating the local energy to pass to jax.lax.scan.

        Args:
            carry (`tuple`): The carry.

        Returns:
            `tuple`: The new carry.
            `jax.numpy.DeviceArray`: The local energy.
        """

        log_psi, params, walker_cfg, sum_O, sum_O_times_local_energy, seed = carry

        subseed, seed = jax.random.split(seed)

        local_energy = self.hamiltonian.calc_local_energy(params, walker_cfg)

        next_walker_cfg, next_log_psi, next_O = self.sampler.next_sample(
            log_psi, params, walker_cfg, seed
        )

        sum_O = jax.tree_util.tree_map(lambda x, y: x + y, sum_O, next_O)
        sum_O_times_local_energy = jax.tree_util.tree_map(
            lambda x, y: x + y * local_energy, sum_O_times_local_energy, next_O
        )

        return (
            next_log_psi,
            params,
            next_walker_cfg,
            sum_O,
            sum_O_times_local_energy,
            subseed,
        ), local_energy

    def calc_local_energies(
        self,
        init_walker_cfg: jnp.DeviceArray,
        init_log_psi: jnp.DeviceArray,
        params: NetParams,
        seed=jax.random.PRNGKey(0),
    ) -> tuple:
        """Calculate the local energies.

        Args:
            init_walker_cfg (`jax.numpy.DeviceArray`): The initial walker configuration.
            init_log_psi (`jax.numpy.DeviceArray`): The initial logarithm of the modulus of the wave function.
            params (`NetParams`): The parameters of the network.
            seed (`jax.random.PRNGKey`): The seed for the random number generator.

        Returns:
            `jax.numpy.DeviceArray`: The local energies.
            `jax.numpy.DeviceArray`: The variational energy.
            `NetParams`: The gradients of the natural logarithm of the modulus of the wave function with respect to the network parameters.
            `NetParams`: The product of the local energies and the gradients of the natural logarithm of the modulus of the wave function with respect to the network parameters.
        """

        carry = (
            init_log_psi,
            params,
            init_walker_cfg,
            jax.tree_util.tree_map(lambda x: x * 0, params),
            jax.tree_util.tree_map(lambda x: x * 0, params),
            seed,
        )

        carry, local_energies = jax.lax.scan(
            self.calc_local_energy_kernel, carry, None, self.batch_size
        )

        E = jnp.sum(local_energies) / self.batch_size

        O = jax.tree_util.tree_map(lambda x: x / self.batch_size, carry[3])

        O_times_local_energy = jax.tree_util.tree_map(
            lambda x: x / self.batch_size, carry[4]
        )

        return local_energies, E, O, O_times_local_energy

    def train(
        self, n_iters: int, params: NetParams, optimizer, expected_E: float
    ) -> Union[Sequence[float], NetParams]:
        """Train the network.

        Args:
            n_iters (`int`): The number of iterations.
            params (`NetParams`): The parameters of the network.

        Returns:
            `NetParams`: The trained parameters.
        """
        opt_state = optimizer.init(params)

        jitted_calc_local_energies = jax.jit(self.calc_local_energies)

        from IPython.display import display, clear_output

        fig, ax = plt.subplots(dpi=150)

        Es = []

        key = jax.random.PRNGKey(0)

        for i in range(n_iters):
            subkey, key = jax.random.split(key)
            walker_cfg = self.ferminet.init_walker_config(1.0, key)
            walker_cfg = jnp.concatenate(walker_cfg, axis=0)

            subkey, key = jax.random.split(key)
            log_psi = self.ferminet.apply(params, walker_cfg)

            local_energies, E, O, O_times_local_energy = jitted_calc_local_energies(
                walker_cfg, log_psi, params
            )

            grad_L = jax.tree_util.tree_map(
                lambda x, y: jnp.nan_to_num(x - y * E), O_times_local_energy, O
            )

            updates, opt_state = optimizer.update(grad_L, opt_state, params)
            params = optax.apply_updates(params, updates)

            Es.append(E)

            if i % 10 == 0:
                ax.cla()

                ax.plot(jnp.abs(jnp.asarray(Es) - (expected_E)))
                ax.set_ylabel(r"$|E_0 - <E>|$")
                ax.set_xlabel("iteration")
                ax.set_yscale("log")

                display(fig)

                print("{:.5f} ± {:.5f}".format(np.mean(Es[-200:]), np.std(Es[-200:])))

            clear_output(wait=True)

        Es = jnp.asarray(Es)

        return params, Es