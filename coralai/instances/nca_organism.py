import torch
import torch.nn as nn

from ..dynamics.nn_lib import ch_norm
from ..dynamics.Organism import Organism

class NCAOrganism(Organism):
    def __init__(self, world, sensors, n_actuators, latent_size = None):
        super(NCAOrganism, self).__init__(world, sensors, n_actuators)

        if latent_size is None:
            latent_size = (self.n_sensors + self.n_actuators) // 2
        self.latent_size = latent_size

        # First convolutional layer
        self.conv = nn.Conv2d(
            self.n_sensors,
            self.latent_size,
            kernel_size=3,
            padding=1,
            padding_mode='circular',
            device=self.world.torch_device,
            bias=False
        )

        # self.latent_conv = nn.Conv2d(
        #     self.latent_size,
        #     self.latent_size,
        #     kernel_size=3,
        #     padding=1,
        #     padding_mode='circular',
        #     device=self.world.torch_device,
        #     bias=False
        # )

        self.latent_conv_2 = nn.Conv2d(
            self.latent_size,
            self.n_actuators,
            kernel_size=3,
            padding=1,
            padding_mode='circular',
            device=self.world.torch_device,
            bias=False
        )


    def forward(self, x=None):
        with torch.no_grad():
            if x is None:
                x=self.world.mem[:, self.sensor_inds, :, :]
            x = self.conv(x)
            x = nn.ReLU()(x)
            x = ch_norm(x)
            x = torch.sigmoid(x)

            # x = self.latent_conv(x)
            # x = nn.ReLU()(x)
            # x = ch_norm(x)
            # x = torch.sigmoid(x)

            x = self.latent_conv_2(x)
            x = nn.ReLU()(x)
            x = ch_norm(x)
            x = torch.sigmoid(x)
            return x


    def perturb_weights(self, perturbation_strength):
        self.conv.weight.data += perturbation_strength * torch.randn_like(self.conv.weight.data)
        # self.latent_conv.weight.data += perturbation_strength * torch.randn_like(self.latent_conv.weight.data)
        self.latent_conv_2.weight.data += perturbation_strength * torch.randn_like(self.latent_conv_2.weight.data)