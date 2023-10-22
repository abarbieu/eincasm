import taichi as ti
import src_ti.Simulation as Simulation
import importlib
importlib.reload(Simulation)
ti.init(arch=ti.gpu)

flow_kernel = ti.Vector.field(2, dtype=ti.i32, shape=5)
flow_kernel[0] = [0, 0]  # ORIGIN
flow_kernel[1] = [-1, 0] # UP
flow_kernel[2] = [0, 1]  # RIGHT
flow_kernel[3] = [1, 0]  # DOWN
flow_kernel[4] = [0, -1] # LEFT

num_com = 10
w,h = 2, 1

sim = Simulation.Simulation(
    'tst', (w,h),
    channels={
        'com': ti.types.vector(n=num_com, dtype=ti.f32),
        'muscles': ti.types.struct(
            flow=ti.types.vector(n=flow_kernel.shape[0], dtype=ti.f32),
            port=ti.f32,
            mine=ti.f32,),
        'macts': ti.types.struct(
            flow=ti.f32,
            port=ti.f32,
            mine=ti.f32),
        'gracts': ti.types.struct(
            flow=ti.types.vector(n=flow_kernel.shape[0], dtype=ti.f32),
            port=ti.f32,
            mine=ti.f32),
        'capital':  {'lims': (0,10)},
        'waste':    {'lims': (0,1)},
        'obstacle': {'lims': (0,1)},
        'port': {
            'lims': (-1,10),
            'metadata': {
                'num_resources': 2,
                'min_regen_amp': 0.5,
                'max_regen_amp': 2,
                'alpha_range': [0.4, 0.9],
                'beta_range': [0.8, 1.2],
                'num_sites_range': [2, 10]}},})

data = sim.init_data()

# ----------------- 3 -----------------


@ti.kernel
def tst_sim(flowm: ti.types.ndarray(), portm: ti.types.ndarray(), minem: ti.types.ndarray()):
    for i,j in ti.ndrange(w,h):
        for k in ti.static(range(flow_kernel.shape[0])):
            flowm[i,j,k] = k
        portm[i,j] = 2
        minem[i,j] = 3

tst_sim(data['muscles']['flow'], data['muscles']['port'], data['muscles']['mine'])

print(data['muscles'])

# ----------------- 2 -----------------
# @ti.dataclass
# class ftype:
#     a: int
#     b: ti.types.vector(3, float)
# # ftype = ti.types.struct(**{'a': ti.i32, 'b': ti.types.vector(3, float)})
# field = ftype.field(shape=(256, 512))
# field.shape # (256, 512)

# @ti.kernel
# def tst_ti(sfield: ti.types.template()):
#     for i,j in sfield:
#         sfield[i,j].a = 2
#         sfield[i,j].b = [1,2,3]

# tst_ti(field)

# @ti.kernel
# def tst_torch(a: ti.types.ndarray(), b: ti.types.ndarray()):
#     for i, j in ti.ndrange(b.shape[0], b.shape[1]):
#         a[i, j] = 4
#         for k in ti.static(range(3)):
#             b[i, j, k] = k * i * j
    
# array_dict = field.to_torch()
# tst_torch(array_dict['a'], array_dict['b'])

# print(array_dict['b'].shape)


# ----------------- 1 -----------------

# import taichi as ti
# import src_ti.eincasm as eincasm
# import src_ti.pcg as pcg_ti

# ti.init(arch=ti.gpu)

# SIM_WIDTH = 640
# SIM_HEIGHT = 480

# # einfield = eincasm.eincell.field(shape=(sim_width, sim_height))

# gray_scale_image = ti.field(dtype=ti.f32, shape=(SIM_WIDTH, SIM_HEIGHT))
# einfield = eincasm.Cell.field(shape=(SIM_WIDTH, SIM_HEIGHT))
# einfield.bla = 2

# @ti.func
# def init_sim(state):
#     for i,j in state:
#         state[i,j]['ob'] = ti.random()

# @ti.kernel
# def fill_image(state: ti.template()):
#     init_sim(state)
#     # Fills the image with random gray
#     for i,j in gray_scale_image:
#         gray_scale_image[i,j] = state[i,j].ob

# fill_image(einfield)
# print(einfield.keys())
# # Creates a GUI of the size of the gray-scale image
# gui = ti.GUI('gray-scale image of random values', (SIM_WIDTH, SIM_HEIGHT))
# while gui.running:
#     gui.set_image(gray_scale_image)
#     gui.show()


