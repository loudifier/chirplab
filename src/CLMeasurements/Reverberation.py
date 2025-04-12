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
from CLAnalysis import write_audio_file

class Reverberation(CLMeasurement):
    measurement_type_name = 'Reverberation'

    output_types = ['WAV file (*.wav)']

    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)
        self.params['type'] = 'Reverberation'

        if len(params)<3: # populate default measurement parameters if none are provided
            self.params['output'] = {
                } # output sample rate is the same as the project analysis sample rate
            
    def measure(self):
        impulse_response = ifft(fft(clp.signals['response']) / fft(clp.signals['stimulus'])).real

        # shift IR to the right by the wavelength of the lowest chirp frequency (to avoid pre-ringing)
        max_wavelength_ms = 1000 * 1 / clp.project['start_freq']
        max_wavelength_ms = max(1.0, max_wavelength_ms) # make sure the IR is shifted at least 1ms, in case the chirp starts above 1kHz
        impulse_response = np.roll(impulse_response, ms_to_samples(max_wavelength_ms))

        # convert to energy time curve
        etc = 20*np.log10(np.abs(impulse_response))

        # store measurement data
        #self.out_ir = impulse_response
        self.out_ir = etc

        # generate sample timestamps for graphs
        self.out_times = samples_to_ms(np.arange(len(impulse_response)) - ms_to_samples(max_wavelength_ms))

        # calculate noise IR
        #if any(clp.signals['noise']):
        #    noise_ir = ifft(fft(clp.signals['noise']) / fft(clp.signals['stimulus'])).real
        #    if self.params['window_mode'] != 'raw':
        #        noise_ir *= window
        #    self.out_noise = np.roll(noise_ir, roll_samples)

        #if self.params['window_mode']!='raw':
        #    # apply offset and scale window appropriately for plotting
        #    self.out_window = np.roll(window, roll_samples) * max(abs(self.out_ir))
        

    def init_tab(self):
        super().init_tab()

        """ self.window_mode = CLParamDropdown('Windowing mode', self.WINDOW_MODES, '')
        window_mode_index = self.window_mode.dropdown.findText(self.params['window_mode'])
        if window_mode_index==-1:
            self.params['window_mode'] = 'auto'
            window_mode_index = 2 # default to adaptive if the project file is mangled
        self.window_mode.dropdown.setCurrentIndex(window_mode_index)
        self.param_section.addWidget(self.window_mode)
        def update_window_mode(index):
            self.params['window_mode'] = self.WINDOW_MODES[index]
            self.truncate.setEnabled(self.params['window_mode']!='raw')
            if self.params['window_mode'] == 'windowed':
                self.window_params.setLocked(False)
            else:
                self.window_params.collapse(animate=self.window_params.isExpanded())
                self.window_params.setLocked(True)
            if self.params['window_mode']=='raw' and self.params['alignment']=='window_start':
                self.alignment.dropdown.setCurrentIndex(3) # change alignment to 'offset'
                return # let update_alignment call measure() and plot()
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
        self.alignment = CLParamDropdown('Time alignment', self.ALIGNMENT_MODES)
        match self.params['alignment']:
            case 'window_start':
                alignment_index = 0
            case 't=0':
                alignment_index = 1
            case 'centered':
                alignment_index = 2
            case 'offset':
                alignment_index = 3
        self.alignment.dropdown.setCurrentIndex(alignment_index)
        self.param_section.addWidget(self.alignment)
        def update_alignment(index):
            match index:
                case 0:
                    self.params['alignment'] = 'window_start'
                case 1:
                    self.params['alignment'] = 't=0'
                case 2:
                    self.params['alignment'] = 'centered'
                case 3:
                    self.params['alignment'] = 'offset'
                    self.offset.setEnabled(True)
            if index < 3:
                self.offset.setEnabled(False)
            self.measure()
            self.plot()
        self.alignment.update_callback = update_alignment

        # fixed offset spinbox
        self.offset = CLParamNum('Offset', self.params['offset'], ['ms', 'samples'], 0, samples_to_ms(len(clp.signals['stimulus'])))
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
                self.offset.max = len(clp.signals['stimulus'])
                self.offset.set_value(ms_to_samples(self.params['offset']))
            else: # changing from samples to ms
                self.offset.set_value(self.params['offset'])
                self.offset.max = samples_to_ms(len(clp.signals['stimulus']))
        self.offset.units_update_callback = update_offset_unit
        self.update_offset_unit = update_offset_unit

        
        # plot window checkbox
        self.plot_window = QCheckBox('Plot window')
        self.plot_window.setChecked(True)
        self.param_section.addWidget(self.plot_window)
        self.plot_window.stateChanged.connect(self.plot)


        # output parameters
        # truncate checkbox
        self.truncate = QCheckBox('Truncate to window')
        self.truncate.setChecked(self.params['output']['truncate'])
        self.truncate.setEnabled(self.params['window_mode']!='raw')
        self.output_section.addWidget(self.truncate)
        def update_truncate(checked):
            self.params['output']['truncate'] = checked
        self.truncate.stateChanged.connect(update_truncate)

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
        self.depth.update_callback = update_depth """

    #def update_tab(self):
    #    self.window_params.update_window_params()
    #    self.update_offset_unit(self.offset.units.currentIndex())

    # time series measurement output requires some base CLMeasurement methods to be overridden
    def save_measurement_data(self, out_path=''):
        out_ir = np.copy(self.out_ir)

        #if self.params['output']['normalize']:
        #    out_ir /= max(abs(out_ir))

        #if self.params['output']['truncate'] and self.params['window_mode']!='raw':
        #    if self.window_start_sample < 0:
        #        out_ir = out_ir[:self.window_end_sample]
        #    else:
        #        out_ir = out_ir[self.window_start_sample:self.window_end_sample]

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
        self.tab.graph.setLabel('left', 'Energy Time Curve')

    def plot(self):
        self.tab.graph.clear()
        
        plot_pen = pg.mkPen(color=clp.PLOT_COLORS[0], width=clp.PLOT_PEN_WIDTH)
        self.tab.graph.plot(self.out_times, self.out_ir, name = self.measurement_type_name, pen=plot_pen) # todo: do something different when plotting a single point (pyqtgraph falls on its face otherwise)
        
        #if clp.project['plot_noise'] and any(self.out_noise):
        #    noise_pen = pg.mkPen(color=clp.NOISE_COLOR, width=clp.PLOT_PEN_WIDTH)
        #    self.tab.graph.plot(self.out_times, self.out_noise, name='Noise Floor', pen=noise_pen)#, color='gray')

        # set the plot range based on the active portion of the impulse response
        #if self.params['window_mode'] == 'raw':
        #    self.tab.graph.setXRange(self.out_times[0], self.out_times[-1])
        #    return # don't plot the window in raw mode
        #if self.params['window_mode'] == 'auto':
        #    max_wavelength_ms = 1000 * 1 / clp.project['start_freq']
        #    graph_min = max(-max_wavelength_ms * 1.1, self.out_times[0])
        #    graph_max = max_wavelength_ms * 2.1
        #else: # 'windowed' case
        #    graph_min = max(-self.params['window_start'] * 1.1, self.out_times[0])
        #    graph_max = self.params['window_end'] * 1.1
        
        # plot the window
        #if self.plot_window.isChecked():
        #    window_pen = pg.mkPen(color=clp.PLOT_COLORS[1], width=clp.PLOT_PEN_WIDTH, style=Qt.DotLine)
        #    self.tab.graph.plot(self.out_times, self.out_window, name='Window', pen=window_pen)
        
        # plot the full range if the window wraps around the beginning/end of the impulse response
        #if self.out_window[-1] > 0:
        #    self.tab.graph.setXRange(self.out_times[0], self.out_times[-1])
        #else:
        #    self.tab.graph.setXRange(graph_min, graph_max) # todo: figure out why plot range is actually lower than graph_min sometimes


        