import CLProject as clp
from CLMeasurements import CLMeasurement
from scipy.fftpack import fft, ifft
from scipy.signal.windows import hann
from CLGui.CLParameter import CLParamDropdown
from CLMeasurements.FrequencyResponse import WindowParamsSection, ms_to_samples, samples_to_ms
import numpy as np
import pyqtgraph as pg

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
                                     # 'window_start' rolls IR by window_start. If window_mode is 'raw', 'window_start' alignment will revert to 'offset'
                                     # 't=0' does not roll the IR. Due to cross-correlation alignment the IR peak will be close to the first (or last) sample of the full IR.
                                     # 'centered' rolls the IR by 1/2 of the total IR length, so the peak will be close to the halfway point
                                     # 'offset' rolls the IR by self.params['offset'] ms
            self.params['offset'] = 10 # length of time in ms to roll the IR to the right when alignment is 'offset'

            self.params['plot_window'] = True # plot the window that is applied to the impulse response (only used in the GUI)

            self.params['output'] = { # impulse response output is a wav file. If a noise sample is present a noise IR will be plotted in the GUI, but not output as a wav file. # todo: add an option to output a second channel or second wav file for noise?
                #'unit': 'Y/X', # unit not actually used for anything, and wouldn't be accurate if output is normalized. Is it needed for anything?
                'truncate': True, # trim impulse response from window_start to window_end (or from the first sample to window_end if alignment is 't=0'). The GUI plot will show the full impulse response range, regardless of the output truncate setting
                'normalize': False, # scale output such that the waveform peaks at 1.0 (or -1.0) full scale
                'bit_depth': '32 float' # options are the same as base project output format, to be used with CLAnalyis.write_audio_file().
                } # output sample rate is the same as the project analysis sample rate
            
    def measure(self):
        impulse_response = ifft(fft(clp.signals['response']) / fft(clp.signals['stimulus'])).real

        if self.params['window_mode'] != 'raw':
            if self.params['window_mode'] == 'auto':
                # calculate window parameters using the same logic as FrequencyResponse adaptive windowing
                max_wavelength_ms = 1000 * 1 / clp.project['start_freq']
                max_wavelength_ms = max(1.0, max_wavelength_ms) # make sure the window is at least 1ms, in case the chirp starts above 1kHz
                window_start = ms_to_samples(max_wavelength_ms)
                fade_in = ms_to_samples(max_wavelength_ms)
                window_end = ms_to_samples(max_wavelength_ms*2)
                fade_out = ms_to_samples(max_wavelength_ms)
            else:
                window_start = ms_to_samples(self.params['window_start'])
                fade_in = ms_to_samples(self.params['fade_in'])
                window_end = ms_to_samples(self.params['window_end'])
                fade_out = ms_to_samples(self.params['fade_out'])

            # construct window
            window = np.zeros(len(impulse_response))
            window[:fade_in] = hann(fade_in*2)[:fade_in]
            window[fade_in:window_start+window_end-fade_out] = np.ones(window_start-fade_in+window_end-fade_out)
            window[window_start+window_end-fade_out:window_start+window_end] = hann(fade_out*2)[fade_out:]
            window = np.roll(window, -window_start)

            # apply window to impulse response
            impulse_response *= window

        # calculate offset from alignment setting
        match self.params['alignment']:
            case 'window_start':
                if self.params['window_mode'] == 'raw':
                    # revert to offset value
                    roll_samples = ms_to_samples(self.params['offset'])
                else:
                    roll_samples = window_start
            case 'centered':
                roll_samples = round(len(impulse_response)/2)
            case 'offset':
                roll_samples = ms_to_samples(self.params['offset'])
            case _: # if alignment is 't=0' or not recognized
                roll_samples = 0

        # apply offset
        impulse_response = np.roll(impulse_response, roll_samples)

        # store measurement data
        self.out_ir = impulse_response

        # calculate noise IR
        if any(clp.signals['noise']):
            noise_ir = ifft(fft(clp.signals['noise']) / fft(clp.signals['stimulus'])).real
            noise_ir *= window
            self.out_noise = np.roll(noise_ir, roll_samples)

        if self.params['plot_window']:
            # apply offset and scale window appropriately for plotting
            self.out_window = np.roll(window, roll_samples) * max(abs(self.out_ir))
        

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
        # todo: make sure to change alignment from 'window_start' to 'offset' if window_mode is changed to 'raw'
        
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
        self.tab.graph.setTitle(self.params['name'])
        self.tab.graph.setLabel('bottom', 'Time (ms)')
        self.tab.graph.setLabel('left', 'Impulse Response')

    def plot(self):
        self.tab.graph.clear()
        
        plot_pen = pg.mkPen(color=clp.PLOT_COLORS[0], width=clp.PLOT_PEN_WIDTH)
        self.tab.graph.plot(self.out_ir, name = self.measurement_type_name, pen=plot_pen) # todo: do something different when plotting a single point (pyqtgraph falls on its face otherwise)
        
        if any(self.out_noise):
            noise_pen = pg.mkPen(color=clp.NOISE_COLOR, width=clp.PLOT_PEN_WIDTH)
            self.tab.graph.plot(self.out_noise, name='Noise Floor', pen=noise_pen)#, color='gray')


        