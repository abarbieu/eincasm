import torch
import taichi as ti
from coralai.substrate.substrate import Substrate
from coralai.instances.nca.nca_vis import NCAVis
from coralai.instances.nca.nca_organism_torch import NCAOrganism
# from coralai.instances.nca.nca_organism_rnn import NCAOrganism

SHAPE = (400, 400)
N_HIDDEN_CHANNELS = 8


def define_substrate(shape, n_hidden_channels):
    ti.init(ti.metal)
    torch_device = torch.device("mps")

    substrate = Substrate(
        shape=shape,
        torch_dtype=torch.float32,
        torch_device=torch_device,
        channels={
            "rgb": ti.types.struct(r=ti.f32, g=ti.f32, b=ti.f32),
            "hidden": ti.types.vector(n=n_hidden_channels, dtype=ti.f32),
        },
    )
    substrate.malloc()
    return substrate


def define_organism(substrate):
    return NCAOrganism(substrate = substrate,
                       sensors = ['rgb', 'hidden'],
                       n_actuators = 3 + N_HIDDEN_CHANNELS,
                       torch_device = substrate.torch_device)


def main():
    substrate = define_substrate(SHAPE, N_HIDDEN_CHANNELS)
    organism = define_organism(substrate)
    vis = NCAVis(substrate, [('rgb', 'r'), ('rgb', 'g'), ('rgb', 'b')])

    while vis.window.running:
        substrate.mem = organism.forward(substrate.mem)
        vis.update()
        if vis.perturbing_weights:
            organism.perturb_weights(vis.perturbation_strength)


if __name__ == "__main__":
    main()