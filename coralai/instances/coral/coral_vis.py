import time
import taichi as ti
import torch
from ...substrate.world import World
from ...analysis.visualization import Visualization


@ti.data_oriented
class CoralVis(Visualization):
    def __init__(
        self,
        world: World,
        chids: list,
        name: str = None,
        scale: int = None,
    ):
        super(CoralVis, self).__init__(world, chids, name, scale)

        chindices = self.world.get_inds_tivec(self.chids)
        if chindices.n != 3:
            raise ValueError("Vis: ch_cmaps must have 3 channels")
        self.chindices = chindices

        if scale is None:
            max_dim = max(self.world.w, self.world.h)
            desired_max_dim = 800
            scale = desired_max_dim // max_dim
        self.scale = scale
        self.img_w = self.world.w * scale
        self.img_h = self.world.h * scale
        self.image = ti.Vector.field(n=3, dtype=ti.f32, shape=(self.img_w, self.img_h))

        self.window = ti.ui.Window(
            f"{self.name}", (self.img_w, self.img_h), fps_limit=200, vsync=True
        )
        self.canvas = self.window.get_canvas()
        self.gui = self.window.get_gui()
        self.paused = False
        self.brush_radius = 4
        self.perturbing_weights = False
        self.perturbation_strength = 0.1
        self.drawing = False
        self.prev_time = time.time()
        self.channel_to_paint = 0


    @ti.kernel
    def add_one(self,
            pos_x: ti.f32,
            pos_y: ti.f32,
            radius: ti.i32,
            channel_to_paint: ti.i32,
            mem: ti.types.ndarray()
        ):
        pass
        # ind_x = int(pos_x * self.w)
        # ind_y = int(pos_y * self.h)
        # offset = int(pos_x) * 3
        # for i, j in ti.ndrange((-radius, radius), (-radius, radius)):
        #     if (i**2) + j**2 < radius**2:
        #         mem[0, channel_to_paint, (i + ind_x) % self.w, (j + ind_y) % self.h] += 1


    @ti.kernel
    def write_to_renderer(self, mem: ti.types.ndarray(), max_vals: ti.types.ndarray(), chindices: ti.template()):
        for i, j in self.image:
            xind = (i//self.scale) % self.w
            yind = (j//self.scale) % self.h
            for k in ti.static(range(3)):
                chid = chindices[k]
                self.image[i, j][k] = mem[0, chid, xind, yind]#/max_vals[k]


    def check_events(self):
        for e in self.window.get_events(ti.ui.PRESS):
            if e.key in  [ti.ui.ESCAPE]:
                exit()
            if e.key == ti.ui.LMB and self.window.is_pressed(ti.ui.SHIFT):
                self.drawing = True
            elif e.key == ti.ui.SPACE:
                self.world.mem *= 0.0
        for e in self.window.get_events(ti.ui.RELEASE):
            if e.key == ti.ui.LMB:
                self.drawing = False


    def render_opt_window(self):
        self.canvas.set_background_color((1, 1, 1))
        opt_w = min(480 / self.img_w, self.img_w)
        opt_h = min(250 / self.img_h, self.img_h * 2)
        with self.gui.sub_window("Options", 0.05, 0.05, opt_w, opt_h) as sub_w:
            self.brush_radius = sub_w.slider_int("Brush Radius", self.brush_radius, 1, 200)
            self.perturbation_strength = sub_w.slider_float("Perturbation Strength", self.perturbation_strength, 0.0, 5.0)
            self.paused = sub_w.checkbox("Pause", self.paused)
            self.perturbing_weights = sub_w.checkbox("Perturb Weights", self.perturbing_weights)
            self.channel_to_paint = sub_w.slider_int("Channel to Paint", self.channel_to_paint, 0, 2)
            sub_w.text("Channel Stats:")
            for channel_name in ['energy', 'infra']:
                chindex = self.world.windex[channel_name]
                max_val = self.world.mem[0, chindex].max()
                min_val = self.world.mem[0, chindex].min()
                avg_val = self.world.mem[0, chindex].mean()
                sum_val = self.world.mem[0, chindex].sum()
                sub_w.text(f"{channel_name}: Max: {max_val:.2f}, Min: {min_val:.2f}, Avg: {avg_val:.2f}, Sum: {sum_val:.2f}")
    

    def update(self):
        if not self.paused:
            self.check_events()
            if self.drawing:
                pos = self.window.get_cursor_pos()
                self.add_one(pos[0], pos[1], self.brush_radius, self.channel_to_paint, self.world.mem)
            max_vals = torch.tensor([self.world.mem[0, ch].max() for ch in self.chindices])
            self.write_to_renderer(self.world.mem, max_vals, self.chindices)
        self.render_opt_window()
        self.canvas.set_image(self.image)
        self.window.show()