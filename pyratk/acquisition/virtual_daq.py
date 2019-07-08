# -*- coding: utf-8 -*-
"""
Virtual DAQ Class.

Description:
DAQ emulation class to playback recorded DAQ datasets in a transparent manner.

Author: Jason Merlo
Maintainer: Jason Merlo (merlojas@msu.edu)
"""
from pyratk.acquisition import daq   # Extention of DAQ object
import threading                     # Used for creating thread and sync events
import time
import h5py
from pyratk.datatypes.ts_data import TimeSeries


class VirtualDAQ(daq.DAQ):
    """Emulate DAQ using HDF5 dataset data."""

    def __init__(self):
        """Create virtual DAQ object to play back recording (hdf5 dataset)."""
        # Attributes
        self.sample_rate = None
        self.sample_chunk_size = None
        self.daq_type = None
        self.num_channels = None

        # start paused if no dataset is selected
        self.paused = True

        self.reset_flag = False

        # Fake sampler period
        self.sample_period = None

        # Create data member to store samples
        self.data = None
        self.ds = None

        # Current time index of recording
        self.sample_index = 0

        # Create sevent for controlling draw events only when there is new data
        self.data_available = threading.Event()

        # Reset/load button sample thread locking
        self.reset_lock = threading.Event()

        self.t_sampling = threading.Thread(target=self.sample_loop)

        self.buffer = []

    def load_dataset(self, ds):
        """Select dataset to read from and loads attributes."""
        if isinstance(ds, h5py._hl.dataset.Dataset):
            self.reset()
            self.ds = ds
            self.sample_index = 0
        else:
            raise(TypeError,
                  "load_dataset expects a h5py dataset type, got", type(ds))

        # Load attributes
        self.sample_rate = ds.attrs["sample_rate"]
        self.sample_chunk_size = ds.attrs["sample_size"]
        self.daq_type = ds.attrs["daq_type"].decode('utf-8')
        self.num_channels = ds.attrs["num_channels"]
        self.sample_period = self.sample_chunk_size / self.sample_rate

        # Create data buffers
        length = 4096
        shape = (self.num_channels, self.sample_chunk_size)
        self.ts_buffer = TimeSeries(length, shape)

    def get_samples(self, stride=1, loop=-1, playback_speed=1.0):
        """Read sample from dataset at sampled speed, or one-by-one."""
        if (self.ds):
            print("(virtual_daq, get_samples) Getting new sample")
            # Read in samples from dataset
            try:
                self.data = self.ds[self.sample_index]
            except IndexError:
                print("Invalid sample index:", self.sample_index)

            # Delay by sample period
            if loop == -1 or loop == 1:
                time.sleep(self.sample_period * playback_speed)
            elif loop == 0:
                print('Stepped:', stride)
            else:
                raise ValueError("Value must be -1, 0, or 1.")

            self.buffer.append((self.data, self.sample_index))
            self.ts_buffer.append(self.data)
            # Set the update event to True once data is read in
            self.data_available.set()

            # Incriment time index and loop around at end of dataset
            self.sample_index = (self.sample_index + stride) % self.ds.shape[0]

            # Return True if more data
            return (self.sample_index + stride) % self.ds.shape[0] / stride < 1.0
        else:
            raise RuntimeError(
                "(VirtualDAQ) Dataset source must be set to get samples")

    def reset(self):
        """Reset all data to beginning of data file and begin playing."""
        self.close()
        self.buffer.clear()
        self.sample_index = 0
        self.reset_flag = True
        self.run()
