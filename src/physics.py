import torch
from typing import Tuple
from src import Simulation, Channel

def random_agent(sim: Simulation, capital: Channel, muscles: Channel, communication: Channel):
    actuators = torch.rand(total_actuator_channels)*2-1
    return actuators

def regen_ports(sim: Simulation, ports: Channel):
    # TODO: take into account resource size and obstacles?
    period = sim.metadata["period"]
    port_id_map = ports.metadata["port_id_map"]
    # port_sizes = ports.metadata["port_sizes"]
    resources = ports.metadata["resources"]
    for resource in resources:
        ports.contents.squeeze(0)[port_id_map == resource.id] += resource.regen_func(period)
        torch.clamp(ports.contents.squeeze(0)[port_id_map == resource.id],
                    ports.allowed_range[0], ports.allowed_range[1],
                    out=ports.contents.squeeze(0)[port_id_map == resource.id])
    num_regens = ports.metadata.get("num_regens", 0)
    ports.metadata.update({"num_regens": num_regens + 1})
    return ports

def grow_muscle_csa(
        sim: Simulation, muscle_radii_ch: Channel, radii_deltas_ch: Channel,
        capital_ch: Channel, metadata: dict):
    
    # TODO: Update to work on batches of environments (simple)
    # TODO: Cost should be able to be lower than 1, right now it is 1:1 + cost
    growth_cost = metadata["growth_cost"]
    muscle_radii = muscle_radii_ch.contents
    radii_deltas = radii_deltas_ch.contents
    capital = capital_ch.contents

    assert capital.min() >= 0, "Capital cannot be negative (before growth)"

    csa_deltas = (muscle_radii + radii_deltas)**2 - muscle_radii**2  # cross-sectional area

    negative_csa_deltas = torch.where(csa_deltas < 0, csa_deltas, torch.zeros_like(csa_deltas))
    positive_csa_deltas = torch.where(csa_deltas > 0, csa_deltas, torch.zeros_like(csa_deltas))

    # Atrophy muscle and convert to capital
    new_csa_mags = muscle_radii**2.0
    total_capital_before = capital.sum() + new_csa_mags.sum()
    new_csa_mags.add_(negative_csa_deltas)

    capital.sub_(torch.sum(negative_csa_deltas, dim=0).mul(1-growth_cost)) # gaining capital from atrophy

    # Grow muscle from capital, if possible
    total_csa_deltas = torch.sum(positive_csa_deltas, dim=0)
    total_csa_deltas_safe = torch.where(total_csa_deltas == 0, torch.zeros_like(total_csa_deltas), total_csa_deltas)
    csa_delta_distribution = positive_csa_deltas.div(total_csa_deltas_safe.unsqueeze(0))
    del total_csa_deltas_safe # TODO: Free CUDA memory? Garbage Collect?  

    capital_consumed = torch.where(total_csa_deltas > capital, capital, total_csa_deltas)
    capital.sub_(capital_consumed)
    capital_consumed.mul_(1-growth_cost)
    # other than inefficiency, exchange rate between capital and muscle area is 1:1 
    new_csa_mags.addcmul_(capital_consumed.unsqueeze(0), csa_delta_distribution) 
    # This is allowed because even with no available capital a muscle may invert its polarity or go to 0 at only a cost of inefficiency
    torch.copysign(torch.sqrt(new_csa_mags), muscle_radii.add(radii_deltas), out=muscle_radii) 

    capital = torch.where(capital < 0.001, torch.zeros_like(capital), capital)
    assert capital.min() >= 0, "Oops, a cell's capital became negative during growth"
    capital_diff = (capital.sum() + new_csa_mags.sum()) - total_capital_before
    assert capital_diff <= 0, f"Oops, capital was invented during growth. Diff: {capital_diff}"

    return muscle_radii, capital


def activate_muscles(muscle_radii: torch.Tensor, activations: torch.Tensor):
    return (torch.sign(muscle_radii) * (muscle_radii ** 2)).mul(activations)    # Activation is a percentage (kinda) of CSA

def activate_port_muscles(
        sim: Simulation, capital_ch: Channel, ports_ch: Channel, port_muscle_radii_ch: Channel,
        port_activations_ch: Channel, metadata: dict):
    # TODO: REALLY? NEGATIVE CAPITAL

    port_cost = metadata["port_cost"]
    capital = capital_ch.contents
    ports = ports_ch.contents
    port_muscle_radii = port_muscle_radii_ch.contents
    port_activations = port_activations_ch.contents
    
    assert capital.min() >= 0, "Capital cannot be negative (before port)"
    desired_delta = activate_muscles(port_muscle_radii, port_activations)
    torch.clamp(desired_delta,
                min=-capital.div(1/port_cost),
                max=torch.min(capital/port_cost, torch.abs(ports)), # Poison costs the same to pump out
                out=desired_delta)
    capital -= desired_delta * port_cost
    capital += torch.copysign(desired_delta,torch.sign(ports)) # can produce negative capital
    torch.clamp(capital, min=0, out=capital) # NOTE: This is a hack to prevent negative capital, fix later
    ports -= desired_delta
    del desired_delta
    assert capital.min() >= 0, "Capital cannot be negative (after port)"
    return capital, ports

def activate_mine_muscles(
        capital_ch: Channel, obstacles_ch: Channel, waste_ch: Channel,
        mine_muscle_radii_ch: Channel, mine_activation_ch: Channel, metadata: dict):
    
    mining_cost = metadata["mining_cost"]
    capital = capital_ch.contents
    obstacles = obstacles_ch.contents
    waste = waste_ch.contents
    mine_muscle_radii = mine_muscle_radii_ch.contents
    mine_activation = mine_activation_ch.contents

    assert capital.min() >= 0, "Capital cannot be negative (before mine)"
    desired_delta = activate_muscles(mine_muscle_radii, mine_activation)
    torch.clamp(desired_delta,
                min=torch.max(-waste, -capital/mining_cost),
                max=torch.min(obstacles, capital/mining_cost),
                out=desired_delta)
    capital -= desired_delta*mining_cost
    obstacles -= desired_delta
    waste += desired_delta
    torch.clamp(capital, min=0, out=capital)

    assert capital.min() >= 0, "Capital cannot be negative (after mine)"
    assert obstacles.min() >= 0, "Obstacle cannot be negative (after mine)"
    return capital, obstacles, waste


def activate_flow_muscles(
        capital_ch: Channel, waste_ch: Channel, obstacles_ch: Channel,
        flow_muscle_radii_ch: Channel, flow_activations_ch: Channel, metadata: dict):
    
    flow_cost = metadata["flow_cost"]
    capital = capital_ch.contents
    waste = waste_ch.contents
    obstacles = obstacles_ch.contents
    flow_muscle_radii = flow_muscle_radii_ch.contents
    flow_activations = flow_activations_ch.contents

    total_capital_before = capital.sum()
    assert capital.min() >= 0, "Capital cannot be negative (before flow)"
    kernel = metadata['kernel']

    # Enforce obstacles
    flow_activations *= (1-obstacles)

    # Invert negative flows across kernel
    roll_shift = (kernel.shape[0]-1)//2
    flows = activate_muscles(flow_muscle_radii, flow_activations)
    positive_flows = torch.where(flows[1:] > 0, flows[1:], torch.zeros_like(flows[1:]))
    negative_flows = torch.where(flows[1:] < 0, flows[1:], torch.zeros_like(flows[1:]))
    flows[1:] = positive_flows.sub(torch.roll(negative_flows, roll_shift, dims=0))
    flows[0] = torch.abs(flows[0]) # Self flow is always positive
    del positive_flows, negative_flows

    # Distribute cytoplasm AND WASTE across flows
    total_flow = torch.sum(flows, dim=0)
    total_flow_desired_safe = torch.where(total_flow == 0, torch.ones_like(total_flow), total_flow)
    flow_distribution = flows.div(total_flow_desired_safe.unsqueeze(0))
    del total_flow_desired_safe

    max_flow_possible = torch.min(capital + waste, capital.div(1+flow_cost))
    total_flow = torch.where(total_flow > max_flow_possible, max_flow_possible, total_flow)
    capital.sub_(total_flow.mul(flow_cost))  # enforce cost of flow before distributing

    mass = capital + waste
    percent_waste = waste.div(torch.where(mass == 0, torch.zeros_like(mass), mass))
    del mass
    waste_out = percent_waste * total_flow
    capital_out = total_flow - waste_out
    capital.sub_(capital_out)
    waste.sub_(waste_out)

    capital_flows = flow_distribution.mul(capital_out.unsqueeze(0))
    waste_flows = flow_distribution.mul(waste_out.unsqueeze(0))
    del waste_out, capital_out

    received_capital = torch.sum(
                            torch.stack(
                                [torch.roll(capital_flows[i], shifts=tuple(map(int, kernel[i])), dims=[0, 1])
                                for i in range(kernel.shape[0])]
                            ), dim=0
                        )
    received_waste = torch.sum(
                            torch.stack(
                                [torch.roll(waste_flows[i], shifts=tuple(map(int, kernel[i])), dims=[0, 1])
                                for i in range(kernel.shape[0])]
                            ), dim=0
                        )
    del capital_flows, waste_flows
    capital.add_(received_capital)
    waste.add_(received_waste)
    del received_capital, received_waste

    # capital = torch.where(capital < 0.01, cfg.zero_tensor, capital) # should be non-negative before this, just for cleanup

    assert capital.min() >= 0, "Capital cannot be negative (after flow)"
    capital_diff = capital.sum() - total_capital_before
    assert capital_diff <= 0, f"Oops, capital was invented during flow. Diff: {capital_diff}"

    return capital, waste
