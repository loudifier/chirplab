from CLGui import CLTab

class FrequencyResponse:
    def __init__(self, name, params):
        self.name = name
        self.params = params
        if not params:
            self.params = { # use default measurement parameters if none are provided
                'window_mode':'windowed', # options are 'raw' for no windowing, 'windowed' for fixed (time-gated) windowing, or 'adaptive' to use an automatically-derived window for each output frequency point
                'window_start': 10, # for fixed window, amount of time in ms included before beginning of impulse response
                'fade_in': 10, # beginning of fixed window ramps up with a half Hann window of width fade_in (must be <= window_start)
                'window_end': 50,
                'fade_out': 25,
                'output':{ # dict containing parameters for output points, frequency range, resolution, etc.
                    'unit': 'dBFS' # fill in the rest later
                    }
                }
        
    def init_tab(self):
        self.tab = CLTab()
        # add measurement parameters
        # run initial measurement and plot results