import torch
import taichi as ti
import numpy as np
import warnings

class Channel:
    def __init__(
            self, id=None, dtype=ti.f32,
            init_func=None,
            lims=None,
            metadata: dict=None, **kwargs):
        self.id = id
        self.lims = lims if lims else (-np.inf, np.inf)
        self.metadata = metadata if metadata is not None else {}
        self.metadata.update(kwargs)
        self.init_func = init_func
        self.dtype = dtype
        self.memblock = None
        self.indices = None
    
    def __getitem__(self, key):
        return self.metadata.get(key)

    def __setitem__(self, key, value):
        self.metadata[key] = value
            
@ti.data_oriented
class World:
    def __init__(self, shape, dtype, channels: dict=None):
        self.shape = (*shape, 0)
        self.channels = {}
        self.memory_allocated = False
        if channels is not None:
            self.add_channels(channels)
        self.tensor_dict = None
        self.mem = None
        self.data = None
        self.index = None

    def add_channel(self, id: str, dtype=ti.f32, **kwargs):
        if self.memory_allocated:
            raise ValueError("When adding channel {id}: Cannot add channel after world memory is allocated (yet).")
        self.channels[id] = Channel(id=id, dtype=dtype, **kwargs)

    def add_channels(self, channels: dict):
        if self.memory_allocated:
            raise ValueError("When adding channels {channels}: Cannot add channels after world memory is allocated (yet).")
        for chid in channels.keys():
            ch = channels[chid]
            if isinstance(ch, Channel):
                 if ch.id is None:
                     ch.id = chid
                 self.channels[id] = ch
            elif isinstance(ch, dict):
                self.add_channel(chid, **ch)
            else:
                self.add_channel(chid, ch)    

    def malloc(self):
        if self.memory_allocated:
            raise ValueError(f"Cannot allocate world memory twice.")
        celltype = ti.types.struct(**{chid: self.channels[chid].dtype for chid in self.channels.keys()})
        self.mem = celltype.field(shape=self.shape[:2])

    def __getitem__(self, key):
        return self.channels.get(key)