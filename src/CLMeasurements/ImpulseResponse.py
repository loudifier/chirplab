import CLProject as clp
from CLMeasurements import CLMeasurement
from CLGui.CLParameter import CLParamDropdown
from CLMeasurements.FrequencyResponse import WindowParamsSection

class ImpulseResponse(CLMeasurement):
    measurement_type_name = 'Impulse Response'

    output_types = ['WAV file (*.wav)']

    WINDOW_MODES = ['raw', 'windowed', 'auto']
    MAX_WINDOW_START = 1000 # fixed impulse response window can start up to 1s before t0
    MAX_WINDOW_END = 10000 # IR window can end up to 10s after t0

    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)
        self.params['type'] = 'ImpulseResponse'

        if len(params)<3: # populate default measurement parameters if none are provided
            self.params['window_mode'] = 'auto' # options are 'raw' for no windowing, 'windowed' for fixed (time-gated) windowing, or 'auto' to use an automatically-derived window based on the lowest chirp frequency
            self.params['window_start'] = 10 # amount of time in ms included before beginning of impulse response
            self.params['fade_in'] = 10 # beginning of window ramps up with a half Hann window of width fade_in (must be <= window_start)
            self.params['window_end'] = 50
            self.params['fade_out'] = 25

            self.params['alignment'] = 'window_start' # options determine how far the calculated impulse response is rolled to the right
                                     # 'window_start' rolls IR by window_start
                                     # 't=0' does not roll the IR. Due to cross-correlation alignment the IR peak will be close to the first (or last) sample of the full IR.
                                     # 'centered' rolls the IR by 1/2 of the total IR length, so the peak will be close to the halfway point

            self.params['plot_window'] = True # plot the window that is applied to the impulse response (only used in the GUI)

            self.params['output'] = { # impulse response output is a wav file
                #'unit': 'Y/X', # unit not actually used for anything, and wouldn't be accurate if output is normalized. Is it needed for anything?
                'truncate': True, # trim impulse response from window_start to window_end (or from the first sample to window_end if alignment is 't=0'). The GUI plot will show the full impulse response range, regardless of the output truncate setting
                'normalize': False, # scale output such that the waveform peaks at 1.0 (or -1.0) full scale
                'bit_depth': '32 float' # options are the same as base project output format, to be used with CLAnalyis.write_audio_file().
                } # output sample rate is the same as the project analysis sample rate
            
    def measure(self):
        pass

    def init_tab(self):
        super().init_tab()

        self.window_mode = CLParamDropdown('Windowing mode', self.WINDOW_MODES, '')
        window_mode_index = self.window_mode.dropdown.findText(self.params['window_mode'])
        if window_mode_index==-1:
            self.params['window_mode'] = 'auto'
            window_mode_index = 2 # default to adaptive if the project file is mangled
        self.window_mode.dropdown.setCurrentIndex(window_mode_index)
        self.param_section.addWidget(self.window_mode)
        def update_window_mode(index):
            self.params['window_mode'] = self.WINDOW_MODES[index]
            if self.params['window_mode'] == 'windowed':
                self.window_params.setLocked(False)
            else:
                self.window_params.collapse(animate=self.window_params.isExpanded())
                self.window_params.setLocked(True)
            self.measure()
            self.plot()
        self.window_mode.update_callback = update_window_mode
        
        # use the window params collapsible section from FrequencyResponse
        self.window_params = WindowParamsSection(self.params)
        if self.params['window_mode'] != 'windowed':
            self.window_params.setLocked(True)
        self.param_section.addWidget(self.window_params)
        def update_window_params():
            self.measure()
            self.plot()
        self.window_params.update_callback = update_window_params

        # alignment dropdown
        
        # plot window checkbox


        # output parameters
        # truncate checkbox

        # normalize checkbox

        # bit depth dropdown

    def update_tab(self):
        self.window_params.update_window_params()

    # time series measurement output requires several base CLMeasurement methods to be overridden
    def save_measurement_data(self, out_path=''):
        pass
    
    def format_graph(self):
        pass

    def plot(self):
        pass


        