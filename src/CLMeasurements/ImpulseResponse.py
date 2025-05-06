import CLProject as clp
from CLMeasurements import CLMeasurement
from scipy.fftpack import fft, ifft
from scipy.signal.windows import hann
from CLGui.CLParameter import CLParamDropdown, CLParamNum
from CLMeasurements.FrequencyResponse import WindowParamsSection, ms_to_samples, samples_to_ms
import numpy as np
import pyqtgraph as pg
from qtpy.QtWidgets import QCheckBox
from qtpy.QtCore import Qt
from pathlib import Path
from CLAnalysis import write_audio_file, resample, find_offset

class ImpulseResponse(CLMeasurement):
    measurement_type_name = 'Impulse Response'

    output_types = ['WAV file (*.wav)']

    WINDOW_MODES = ['raw', 'windowed', 'auto']
    MAX_WINDOW_START = 1000 # fixed impulse response window can start up to 1s before t0
    MAX_WINDOW_END = 10000 # IR window can end up to 10s after t0

    ALIGNMENT_MODES = ['window start', 't0', 'centered', 'fixed offset']
    TRUNCATE_MODES = ['window end', 'fixed length', 'full length']

    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)

        if len(params)<3: # populate default measurement parameters if none are provided
            self.params['window_mode'] = 'auto' # options are 'raw' for no windowing, 'windowed' for fixed (time-gated) windowing, or 'auto' to use an automatically-derived window based on the lowest chirp frequency
            self.params['window_start'] = 10 # amount of time in ms included before beginning of impulse response
            self.params['fade_in'] = 10 # beginning of window ramps up with a half Hann window of width fade_in (must be <= window_start)
            self.params['window_end'] = 50
            self.params['fade_out'] = 25
            self.params['ref_channel'] = 0 # signal to use as the reference for the impulse response calculation, where the impulse response is a model of the transfer function between an input signal (the ref_channel) and and output signal (the input channel selected in the main project). When ref_channel is 0, the stimulus signal is used as the reference
            self.params['timing_channel'] = 0 # When ref_channel is 0, the input channel to use as a timing reference. This allows time alignment relative to the mean group delay of the timing reference, without being affected by variations in the reference channel's frequency or phase response. When set to 0, the input channel time alignment is used.

            self.params['alignment'] = 'window_start' # options determine how far the calculated impulse response is rolled to the right
                                     # 'window_start' rolls IR by window_start. If window_mode is 'raw', 'window_start' alignment will revert to 'offset'
                                     # 't0' does not roll the IR. Due to cross-correlation alignment the IR peak will be close to the first (or last) sample of the full IR.
                                     # 'centered' rolls the IR by 1/2 of the total IR length, so the peak will be close to the halfway point. truncate_mode will be changed to 'full'
                                     # 'offset' rolls the IR by self.params['offset'] ms
            self.params['offset'] = 10 # length of time in ms to roll the IR to the right when alignment is 'offset'

            self.params['output'] = { # impulse response output is a wav file. If a noise sample is present a noise IR will be plotted in the GUI, but not output as a wav file. # todo: add an option to output a second channel or second wav file for noise?
                #'unit': 'Y/X', # unit not actually used for anything, and wouldn't be accurate if output is normalized. Is it needed for anything?
                # the total output length includes any time preceeding t0 determined by alignment settings, plus the time after t0 determined by truncation settings
                'truncate_mode': 'window_end', # length of time to cut off impulse response after t0
                               # 'window_end' truncates the impulse response to window_end
                               # 'fixed' truncates to self.params['output']['truncate_length'] ms after t0
                               # 'full' does not trim the impulse response at all. If window_start is 'centered', truncate_mode will be set to 'full'
                'truncate_length': 100, # length of impulse response in ms after t0, when truncate_mode is 'fixed'
                'normalize': False, # scale output such that the waveform peaks at 1.0 (or -1.0) full scale
                'bit_depth': '32 float' # options are the same as base project output format, to be used with CLAnalyis.write_audio_file().
                } # output sample rate is the same as the project analysis sample rate
            
    def measure(self):
        def get_input_signal(channel, delay): # mostly the same process as CLAnalysis.read_response() # todo: consider refactoring CLAnalysis.read_response(), this, and PhaseResponse to reduce duplication
            # get signal from raw input channel at the given delay. Ued to get reference signal and timing reference signals
            if clp.signals['raw_response'].ndim > 1:
                input_signal = clp.signals['raw_response'][:,channel-1]
            else:
                input_signal = clp.signals['raw_response']
            if clp.project['sample_rate'] != clp.IO['input']['sample_rate']:
                input_signal = resample(input_signal, clp.IO['input']['sample_rate'], clp.project['sample_rate'])

            start_padding = max(0, -delay)
            delay = delay + start_padding
            end_padding = max(0, len(clp.signals['stimulus']) - (len(input_signal) - delay))
            input_signal = np.concatenate([np.zeros(start_padding), input_signal, np.zeros(end_padding)])

            return input_signal[delay:delay + len(clp.signals['stimulus'])]

        if self.params['ref_channel']:
            # get signal from reference channel at same timing as input channel
            reference = get_input_signal(self.params['ref_channel'], clp.IO['input']['delay'])
            response = clp.signals['response']
        else:
            # use stimulus signal as the reference (and potentially use a different channel as the timing reference)
            reference = clp.signals['stimulus']

            if (self.params['timing_channel']==0) or (self.params['timing_channel']==clp.project['input']['channel']):
                # skip time alignment if input channel is referenced to itself
                response = clp.signals['response']
            else:
                # get the time reference aligned to main response
                time_reference = get_input_signal(self.params['timing_channel'], clp.IO['input']['delay'])

                # calculate the offset between the time reference and the stimulus
                time_reference_offset = find_offset(time_reference, clp.signals['stimulus'])

                # get the response signal trimmed to the time reference delay
                response = get_input_signal(clp.project['input']['channel'], clp.IO['input']['delay'] + time_reference_offset)


        # calculate raw impulse response
        impulse_response = ifft(fft(response) / fft(reference)).real
        

        # calculate window parameters (parameters are sometimes used even when window isn't applied)
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

        if self.params['window_mode'] != 'raw':
            # construct window
            window = np.zeros(len(impulse_response))
            window[:fade_in] = hann(fade_in*2)[:fade_in]
            window[fade_in:window_start+window_end-fade_out] = np.ones(window_start-fade_in+window_end-fade_out)
            window[window_start+window_end-fade_out:window_start+window_end] = hann(fade_out*2)[fade_out:]
            window = np.roll(window, -window_start)

            # apply window to impulse response
            impulse_response *= window

        # calculate offset from alignment setting
        roll_samples = self.calc_offset_samples()

        # apply offset
        impulse_response = np.roll(impulse_response, roll_samples)

        # store measurement data
        self.out_ir = impulse_response

        # store bounds for truncation
        # todo: handle edge cases of very long windows/offsets longer than the IR
        # initialize to full range and override based on truncation settings
        self.out_start_sample = 0 # any reason for this to not be 0?
        self.out_end_sample = len(impulse_response)-1 # truncate_mode='full' case
        if self.params['output']['truncate_mode'] == 'window_end':
            self.out_end_sample = roll_samples + window_end
        if self.params['output']['truncate_mode'] == 'fixed':
            self.out_end_sample = roll_samples + ms_to_samples(self.params['output']['truncate_length']) # todo: warn when truncation is shorter than window_end?
        # todo: warn when window_start is negative (and shows up at the end of the IR)? 

        # generate sample timestamps for graphs
        self.out_times = samples_to_ms(np.arange(len(impulse_response)) - roll_samples)

        # calculate noise IR
        if any(clp.signals['noise']):
            noise_ir = ifft(fft(clp.signals['noise']) / fft(clp.signals['stimulus'])).real
            if self.params['window_mode'] != 'raw':
                noise_ir *= window
            self.out_noise = np.roll(noise_ir, roll_samples)

        if self.params['window_mode']!='raw':
            # apply offset and scale window appropriately for plotting
            self.out_window = np.roll(window, roll_samples) * max(abs(self.out_ir))

    def calc_offset_samples(self):
        match self.params['alignment']:
            case 'window_start':
                if self.params['window_mode'] == 'raw':
                    # revert to offset value
                    return ms_to_samples(self.params['offset'])
                else:
                    # some code duplication from measure()
                    if self.params['window_mode'] == 'auto':
                        # calculate window parameters using the same logic as FrequencyResponse adaptive windowing
                        max_wavelength_ms = 1000 * 1 / clp.project['start_freq']
                        max_wavelength_ms = max(1.0, max_wavelength_ms) # make sure the window is at least 1ms, in case the chirp starts above 1kHz
                        return ms_to_samples(max_wavelength_ms)
                    else:
                        return ms_to_samples(self.params['window_start'])
            case 'centered':
                return round(len(clp.signals['stimulus'])/2)
            case 'offset':
                return ms_to_samples(self.params['offset'])
        # if alignment is 't0' or not recognized
        return 0

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
            if self.params['window_mode']=='raw':
                if self.params['alignment'] == 'window_start':
                    self.alignment.dropdown.setCurrentIndex(3) # change alignment to 'offset'
                if self.params['output']['truncate_mode'] == 'window_end':
                    self.truncate_mode.dropdown.setCurrentIndex(1)
                self.plot_window.setEnabled(False)
                return # alignment and/or window updates call measure() and plot()
            else:
                self.plot_window.setEnabled(True)
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

        # reference channel dropdown
        self.ref_channel = CLParamDropdown('Reference signal', ['stimulus'])
        self.param_section.addWidget(self.ref_channel)
        def update_ref_channel(index):
            self.params['ref_channel'] = index
            self.timing_channel.setEnabled(index==0)
            self.measure()
            self.plot()
        self.ref_channel.update_callback = update_ref_channel

        # time reference channel dropdown
        self.timing_channel = CLParamDropdown('Timing reference', ['input'])
        self.timing_channel.setEnabled(self.params['ref_channel']==0)
        self.param_section.addWidget(self.timing_channel)
        def update_timing_channel(index): # todo: check more thoroughly for corner cases
            self.params['timing_channel'] = index
            self.measure()
            self.plot()
        self.timing_channel.update_callback = update_timing_channel
        
        def update_num_channels(num_channels):
            channel_list = ['channel '+str(chan) for chan in range(1, num_channels+1)]

            self.ref_channel.dropdown.blockSignals(True)
            self.ref_channel.dropdown.clear()
            self.ref_channel.dropdown.addItems(['stimulus signal'] + channel_list)
            if self.params['ref_channel'] > num_channels:
                self.params['ref_channel'] = 0
            self.ref_channel.dropdown.setCurrentIndex(self.params['ref_channel'])
            self.ref_channel.dropdown.blockSignals(False)

            self.timing_channel.dropdown.blockSignals(True)
            self.timing_channel.dropdown.clear()
            self.timing_channel.dropdown.addItems(['input channel'] + channel_list)
            if self.params['timing_channel'] > num_channels:
                self.params['timing_channel'] = 0
            self.timing_channel.dropdown.setCurrentIndex(self.params['timing_channel'])
            self.timing_channel.dropdown.blockSignals(False)
        self.update_num_channels = update_num_channels
        self.update_num_channels(clp.IO['input']['channels'])

        # alignment dropdown
        self.alignment = CLParamDropdown('Time alignment', self.ALIGNMENT_MODES)
        match self.params['alignment']:
            case 'window_start':
                alignment_index = 0
            case 't0':
                alignment_index = 1
            case 'centered':
                alignment_index = 2
            case 'offset':
                alignment_index = 3
        self.alignment.dropdown.setCurrentIndex(alignment_index)
        self.param_section.addWidget(self.alignment)
        def update_alignment(index):
            if (index==0) and (self.params['window_mode']=='raw'):
                self.alignment.revert()
                return
            
            if index < 3:
                self.offset.setEnabled(False)
            
            match index:
                case 0:
                    self.params['alignment'] = 'window_start'
                case 1:
                    self.params['alignment'] = 't0'
                case 2:
                    self.params['alignment'] = 'centered'
                    self.params['output']['truncate_mode'] = 'full'
                    self.truncate_mode.dropdown.blockSignals(True)
                    self.truncate_mode.dropdown.setCurrentIndex(2)
                    self.truncate_mode.last_index = 2
                    self.truncate_mode.dropdown.blockSignals(False)
                case 3:
                    self.params['alignment'] = 'offset'
                    self.offset.setEnabled(True)
            self.measure()
            self.plot()
        self.alignment.update_callback = update_alignment

        # fixed offset spinbox
        self.offset = CLParamNum('Offset', self.params['offset'], ['ms', 'samples'], 0, samples_to_ms(len(clp.signals['stimulus'])-1))
        self.offset.setEnabled(self.params['alignment']=='offset')
        self.param_section.addWidget(self.offset)
        def update_offset(new_val):
            if self.offset.units.currentIndex(): # samples
                self.params['offset'] = samples_to_ms(new_val)
            else: # ms
                self.params['offset'] = new_val
            self.measure()
            self.plot()
        self.offset.update_callback = update_offset
        def update_offset_unit(index):
            if index: # changing from ms to samples
                self.offset.max = len(clp.signals['stimulus'])-1
                self.offset.set_value(ms_to_samples(self.params['offset']))
                self.offset.set_numtype('int')
            else: # changing from samples to ms
                self.offset.set_numtype('float')
                self.offset.set_value(self.params['offset'])
                self.offset.max = samples_to_ms(len(clp.signals['stimulus'])-1)
        self.offset.units_update_callback = update_offset_unit
        self.update_offset_unit = update_offset_unit


        # output parameters
        # truncate mode dropdown
        self.truncate_mode = CLParamDropdown('Truncation mode', self.TRUNCATE_MODES)
        if self.params['output']['truncate_mode'] == 'fixed':
            self.truncate.dropdown.setCurrentIndex(1)
        if self.params['output']['truncate_mode'] == 'full':
            self.truncate.dropdown.setCurrentIndex(2)
        self.output_section.addWidget(self.truncate_mode)
        def update_truncate_mode(index):
            if self.params['alignment'] == 'centered':
                self.truncate_mode.revert()
                return

            match index:
                case 0:
                    if self.params['window_mode'] == 'raw':
                        self.truncate_mode.revert()
                        return
                    self.params['output']['truncate_mode'] = 'window_end'
                case 1:
                    self.params['output']['truncate_mode'] = 'fixed'
                case 2:
                    self.params['output']['truncate_mode'] = 'full'
            self.truncate_length.setEnabled(index==1)
            self.measure()
            self.plot()
        self.truncate_mode.update_callback = update_truncate_mode

        # fixed truncation length spinbox
        self.truncate_length = CLParamNum('Fixed length (after t0)', self.params['output']['truncate_length'], ['ms', 'samples'], 0, samples_to_ms(len(clp.signals['stimulus'])-1 - self.calc_offset_samples()))
        self.truncate_length.setEnabled(self.params['output']['truncate_mode']=='fixed')
        self.output_section.addWidget(self.truncate_length)
        def update_truncate_length(new_val):
            if self.truncate_length.units.currentIndex(): # samples
                self.params['output']['truncate_length'] = samples_to_ms(new_val)
            else: # ms
                self.params['output']['truncate_length'] = new_val
        self.truncate_length.update_callback = update_truncate_length
        def update_truncate_length_units(index):
            if index: # samples
                self.truncate_length.max = ms_to_samples(len(clp.signals['stimulus'])-1 - self.calc_offset_samples())
                self.truncate_length.set_value(ms_to_samples(self.params['output']['truncate_length']))
                self.truncate_length.set_numtype('int')
            else: # ms
                self.truncate_length.set_numtype('float')
                self.truncate_length.set_value(self.params['output']['truncate_length'])
                self.truncate_length.max = len(clp.signals['stimulus'])-1 - self.calc_offset_samples()
            self.measure()
            self.plot()
        self.truncate_length.units_update_callback = update_truncate_length_units
        self.update_truncate_length_units = update_truncate_length_units

        # normalize checkbox
        self.normalize = QCheckBox('Normalize to full scale')
        self.normalize.setChecked(self.params['output']['normalize'])
        self.output_section.addWidget(self.normalize)
        def update_normalize(checked):
            self.params['output']['normalize'] = checked
        self.normalize.stateChanged.connect(update_normalize)

        # bit depth dropdown
        self.depth = CLParamDropdown('Bit depth', clp.OUTPUT_BIT_DEPTHS)
        depth_index = self.depth.dropdown.findText(self.params['output']['bit_depth'])
        if depth_index != -1:
            self.depth.dropdown.setCurrentIndex(depth_index)
        self.output_section.addWidget(self.depth)
        def update_depth(index):
            self.params['output']['bit_depth'] = clp.OUTPUT_BIT_DEPTHS[index]
        self.depth.update_callback = update_depth

        # plot window checkbox
        self.plot_window = QCheckBox('Plot window')
        if self.params['window_mode'] == 'raw':
            self.plot_window.setEnabled(False)
        self.plot_window.setChecked(True)
        self.output_section.addWidget(self.plot_window)
        self.plot_window.stateChanged.connect(self.plot)

    def update_tab(self):
        self.window_params.update_window_params()
        self.update_offset_unit(self.offset.units.currentIndex())
        self.update_truncate_length_units(self.truncate_length.units.currentIndex())
        self.update_num_channels(clp.IO['input']['channels'])

    # time series measurement output requires some base CLMeasurement methods to be overridden
    def save_measurement_data(self, out_path=''):
        out_ir = np.copy(self.out_ir[self.out_start_sample:self.out_end_sample])

        if self.params['output']['normalize']:
            out_ir /= max(abs(out_ir))

        if not out_path:
            # no path given, output a wav file using the project and measurement name in the current directory
            out_path = Path(clp.project_file).stem + '_' + self.params['name'] + '.wav'
        else:
            # path given, check if it is a file name or just an output directory
            if Path(out_path).is_dir():
                out_path = Path(out_path) / Path(Path(clp.project_file).stem + '_' + self.params['name'] + '.wav') # add default file name to directory
            # else leave provided file name/path as-is

        write_audio_file(out_ir, out_path, clp.project['sample_rate'], self.params['output']['bit_depth'])

    def format_graph(self):
        self.tab.graph.setTitle(self.params['name'])
        self.tab.graph.setLabel('bottom', 'Time (ms)')
        self.tab.graph.setLabel('left', 'Impulse Response')

    def plot(self):
        self.tab.graph.clear()
        
        plot_pen = pg.mkPen(color=clp.PLOT_COLORS[0], width=clp.PLOT_PEN_WIDTH)
        self.tab.graph.plot(self.out_times, self.out_ir, name = self.measurement_type_name, pen=plot_pen) # todo: do something different when plotting a single point (pyqtgraph falls on its face otherwise)
        
        if clp.project['plot_noise'] and any(self.out_noise):
            noise_pen = pg.mkPen(color=clp.NOISE_COLOR, width=clp.PLOT_PEN_WIDTH)
            self.tab.graph.plot(self.out_times, self.out_noise, name='Noise Floor', pen=noise_pen)#, color='gray')

        # plot the window
        if self.plot_window.isChecked() and (self.params['window_mode'] != 'raw'):
            window_pen = pg.mkPen(color=clp.PLOT_COLORS[1], width=clp.PLOT_PEN_WIDTH, style=Qt.DotLine)
            self.tab.graph.plot(self.out_times, self.out_window, name='Window', pen=window_pen)
        
        # set the plot range based on the truncation settings
        self.tab.graph.setXRange(self.out_times[self.out_start_sample], self.out_times[self.out_end_sample])

        return
        # plot the full range if the window wraps around the beginning/end of the impulse response ?
        if self.out_window[-1] > 0:
            self.tab.graph.setXRange(self.out_times[0], self.out_times[-1])
        