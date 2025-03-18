import CLProject as clp
from CLGui import CLTab, CLParameter, CLParamNum, CLParamDropdown, CLParamFile, QCollapsible, QHSeparator, CalibrationDialog
from CLAnalysis import generate_stimulus, read_audio_file, read_response, generate_output_stimulus, generate_stimulus_file, audio_file_info, write_audio_file
import numpy as np
from qtpy.QtWidgets import QPushButton, QCheckBox, QAbstractSpinBox, QFileDialog, QComboBox, QFrame, QVBoxLayout
from qtpy.QtCore import Signal, Slot, QObject
import pyqtgraph as pg
from engineering_notation import EngNumber
import DeviceIO
from time import time


# First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
class ChirpTab(CLTab):
    def __init__(self):
        super().__init__()
        #self.graph.axes.set_title('Stimulus Signal / Captured Response')
        self.graph.setTitle('Stimulus Signal / Captured Response') 
        self.graph.setLabel('left', 'Amplitude (FS)') # option to display units in V or Pa?
        
        
        # Chirp parameters section
        self.chirp_params = ChirpParameters(self)
        self.panel.addWidget(self.chirp_params)

        self.panel.addWidget(QHSeparator())
        
        
        # Output file or audio device section
        self.output_params = OutputParameters(self)
        self.panel.addWidget(self.output_params)


        self.panel.addWidget(QHSeparator())
        
        
        # Input file or audio device section
        self.input_params = InputParameters(self)
        self.panel.addWidget(self.input_params)
        

    def update_stimulus(self):
        # generate new stimulus from chirp and analysis parameters
        generate_stimulus()
        
        # update chirp tab graph and rerun measurements
        self.analyze()
        
        
    def analyze(self):
        # first, verify input file is valid
        #self.update_input_file()
        
        # if input signal was found read it in, otherwise blank out response
        if clp.IO['input']['length_samples']:
            read_response() # reads in raw response, resamples if necessary, gets desired channel, trims/aligns, and puts segment containing response chirp in clp.signals['response'] (and noise sample in clp.signals['noise'])
        else:
            clp.signals['response'] = np.zeros(len(clp.signals['stimulus']))
            clp.signals['noise'] = []

        # update chirp tab graph
        self.plot()

        # update measurements
        for measurement in clp.measurements:
            measurement.update_tab()
            measurement.measure()
            measurement.plot()
            measurement.format_graph()
    
    # plot stimulus, response, and noise
    def plot(self):
        self.graph.clear()
        
        if self.chirp_params.chirp_length.units.currentIndex() == 0: #times in seconds
            times = np.arange(len(clp.signals['stimulus']))/clp.project['sample_rate'] - clp.project['pre_sweep']
            self.graph.setLabel('bottom', 'Time (seconds)')
        else: #times in samples
            times = np.arange(len(clp.signals['stimulus'])) - round(clp.project['pre_sweep']*clp.project['sample_rate'])
            self.graph.setLabel('bottom', 'Time (samples)')
        
        signal_pen = pg.mkPen(color=clp.PLOT_COLORS[0], width = clp.PLOT_PEN_WIDTH)
        self.graph.plot(times, clp.signals['stimulus'], name='stimulus', pen=signal_pen)
        
        response_pen = pg.mkPen(color=clp.PLOT_COLORS[1], width = clp.PLOT_PEN_WIDTH)
        self.graph.plot(times, clp.signals['response'], name='response', pen=response_pen)
        
        if any(clp.signals['noise']):
            noise_pen = pg.mkPen(color=clp.NOISE_COLOR, width = clp.PLOT_PEN_WIDTH)
            self.graph.plot(times, clp.signals['noise'], name='noise sample', pen=noise_pen)


class ChirpParameters(QCollapsible):
    def __init__(self, chirp_tab):
        super().__init__('Chirp Parameters')

        self.start_freq = CLParamNum('Start Freq', clp.project['start_freq'], 'Hz', clp.MIN_CHIRP_FREQ, clp.project['sample_rate']/2)
        self.addWidget(self.start_freq)
        self.expand() # needs to be called after the first widget is added for some reason
        def update_start_freq(new_value):
            if new_value == self.stop_freq.value: # catch any other invalid values (min/max are caught automatically)
                # don't catch start_freq being higher than stop_freq. Down-swept chirps technically still work with most measurements
                self.start_freq.revert() # revert and do nothing
            else:
                clp.project['start_freq'] = float(new_value) # apply the new value to the project
                chirp_tab.update_stimulus() # update the stimulus (which updates the measurements)
        self.start_freq.update_callback = update_start_freq
        
        self.stop_freq = CLParamNum('Stop Freq', clp.project['stop_freq'], 'Hz', clp.MIN_CHIRP_FREQ, clp.project['sample_rate']/2)
        self.addWidget(self.stop_freq)
        def update_stop_freq(new_value):
            if new_value == self.start_freq.value:
                self.stop_freq.revert()
            else:
                clp.project['stop_freq'] = float(new_value)
                chirp_tab.update_stimulus()
        self.stop_freq.update_callback = update_stop_freq
        
        self.chirp_length = CLParamNum('Chirp Length', clp.project['chirp_length'], ['Sec','Samples'], clp.MIN_CHIRP_LENGTH, clp.MAX_CHIRP_LENGTH, 'float')
        self.addWidget(self.chirp_length)
        def update_chirp_length(new_value):
            if self.chirp_length.units.currentIndex()==0: # update seconds directly
                clp.project['chirp_length'] = self.chirp_length.value
            else: # convert samples to seconds
                clp.project['chirp_length'] = self.chirp_length.value / clp.project['sample_rate']
            chirp_tab.update_output_length()
            chirp_tab.update_stimulus()
        self.chirp_length.update_callback = update_chirp_length
        def update_chirp_length_units(index):
            if index==0: # seconds
                self.chirp_length.set_numtype('float')
                self.chirp_length.min = clp.MIN_CHIRP_LENGTH
                self.chirp_length.max = clp.MAX_CHIRP_LENGTH
                self.chirp_length.set_value(clp.project['chirp_length'])
            else:
                self.chirp_length.min = clp.MIN_CHIRP_LENGTH*clp.project['sample_rate']
                self.chirp_length.max = clp.MAX_CHIRP_LENGTH*clp.project['sample_rate']
                self.chirp_length.set_value(clp.project['chirp_length']*clp.project['sample_rate'])
                self.chirp_length.set_numtype('int')
            chirp_tab.plot() # works for default graph zoom level. todo: check the X axis limits and adjust them to match the current units
        self.chirp_length.units_update_callback = update_chirp_length_units
        
        
        # Chirp analysis parameters
        self.analysis_params = QCollapsible('Analysis Parameters')
        self.addWidget(self.analysis_params)
        
        self.sample_rate = CLParamDropdown('Sample Rate', ['use input rate'], 'Hz', editable=True)
        self.sample_rate.dropdown.addItems([str(EngNumber(rate)) for rate in clp.STANDARD_SAMPLE_RATES])
        if not clp.project['use_input_rate']:
            sample_rate_index = self.sample_rate.dropdown.findText(str(EngNumber(clp.project['sample_rate'])))
            if sample_rate_index != -1:
                self.sample_rate.dropdown.setCurrentIndex(sample_rate_index)
            else:
                self.sample_rate.dropdown.setCurrentText(str(EngNumber(clp.project['sample_rate'])))
        self.analysis_params.addWidget(self.sample_rate)
        def update_sample_rate(index=-1, new_rate=None): # fires when text is entered or when an option is selected from the dropdown.
            # index is provided by regular dropdown callback, but is ignored here
            # new_rate is specified when manually setting the analysis sample rate from code outside of the analysis parameters (i.e. from the input parameters when 'use input rate' is selected)
            if new_rate is None:
                new_rate = sample_rate_str2num(self.sample_rate.value)
            if new_rate:
                if self.sample_rate.dropdown.currentIndex()==0 and 'input' in self.sample_rate.value:
                    clp.project['use_input_rate'] = True
                    if clp.IO['input']['sample_rate']:
                        clp.project['sample_rate'] = clp.IO['input']['sample_rate']
                else:
                    clp.project['use_input_rate'] = False
                    clp.project['sample_rate'] = new_rate
                update_pre_sweep_units(self.pre_sweep.units.currentIndex())
                update_post_sweep_units(self.post_sweep.units.currentIndex())
                chirp_tab.update_stimulus()
        self.sample_rate.update_callback = update_sample_rate
        chirp_tab.update_sample_rate = update_sample_rate
        def sample_rate_str2num(str_rate):
            if 'input' in str_rate:
               self.sample_rate.last_value = 'use input rate'
               self.sample_rate.dropdown.setCurrentIndex(0)
               return clp.IO['input']['sample_rate']
            try:
                EngNumber(str_rate) # if the input text can't be construed as a number then revert and return 0
            except:
                self.sample_rate.dropdown.setCurrentText(self.sample_rate.last_value)
                return 0
            num_rate = round(float(EngNumber(str_rate)))
            num_rate = min(max(num_rate, clp.MIN_SAMPLE_RATE), clp.MAX_SAMPLE_RATE)
            self.sample_rate.last_value = str(EngNumber(num_rate))
            self.sample_rate.dropdown.setCurrentText(str(EngNumber(num_rate))) # todo: handle corner case where this can fire recalculation when clicking the dropdown after typing in a sample rate 
            return num_rate
        
        # pre sweep - s/sample dropdown
        self.pre_sweep = CLParamNum('Pre Sweep', clp.project['pre_sweep'], ['Sec', 'Samples'], 0, clp.MAX_ZERO_PAD, 'float')
        self.analysis_params.addWidget(self.pre_sweep)
        def update_pre_sweep(new_value):
            if self.pre_sweep.units.currentIndex()==0: # sec
                clp.project['pre_sweep'] = new_value
            else: # samples
                clp.project['pre_sweep'] = new_value / clp.project['sample_rate']
            chirp_tab.update_stimulus()
        self.pre_sweep.update_callback = update_pre_sweep
        def update_pre_sweep_units(index):
            if index==0: # sec
                self.pre_sweep.max = clp.MAX_ZERO_PAD
                self.pre_sweep.set_numtype('float')
                self.pre_sweep.set_value(clp.project['pre_sweep'])
            else: # samples
                self.pre_sweep.max = clp.MAX_ZERO_PAD * clp.project['sample_rate']
                self.pre_sweep.set_value(clp.project['pre_sweep'] * clp.project['sample_rate'])
                self.pre_sweep.set_numtype('int')
        self.pre_sweep.units_update_callback = update_pre_sweep_units
        
        # post sweep - s/sample dropdown
        self.post_sweep = CLParamNum('Post Sweep', clp.project['post_sweep'], ['Sec', 'Samples'], 0, clp.MAX_ZERO_PAD, 'float')
        self.analysis_params.addWidget(self.post_sweep)
        def update_post_sweep(new_value):
            if self.post_sweep.units.currentIndex()==0: # sec
                clp.project['post_sweep'] = new_value
            else: # samples
                clp.project['post_sweep'] = new_value / clp.project['sample_rate']
            chirp_tab.update_stimulus()
        self.post_sweep.update_callback = update_post_sweep
        def update_post_sweep_units(index):
            if index==0: # sec
                self.post_sweep.max = clp.MAX_ZERO_PAD
                self.post_sweep.set_numtype('float')
                self.post_sweep.set_value(clp.project['post_sweep'])
            else: # samples
                self.post_sweep.max = clp.MAX_ZERO_PAD * clp.project['sample_rate']
                self.post_sweep.set_value(clp.project['post_sweep'] * clp.project['sample_rate'])
                self.post_sweep.set_numtype('int')
        self.post_sweep.units_update_callback = update_post_sweep_units


class OutputParameters(QCollapsible):
    def __init__(self, chirp_tab):
        super().__init__('Output')

        self.mode_dropdown = QComboBox()
        self.addWidget(self.mode_dropdown)
        self.mode_dropdown.addItems(['File','Device'])
        def update_output_mode(index):
            # inelegant to recreate the panel each time the mode is updated, but FileOutput/DeviceOutput both change shared clp.project and actually switching still feels fast in the GUI
            # todo: check for weird memory leaks or corner cases with .replaceWidget() and .close(). Searching for anything related to replacing/deleting widgets seems to show a lot of different approaches with differing results
            current_widget = self.output_frame.layout().itemAt(0).widget()
            if index:
                clp.project['output']['mode'] = 'device'
                self.device_output = DeviceOutput(chirp_tab)
                self.output_frame.layout().replaceWidget(current_widget, self.device_output)
                if clp.project['input']['mode'] == 'device':
                    chirp_tab.input_params.device_input.capture.setText('Play and Capture')
            else:
                clp.project['output']['mode'] = 'file'
                self.file_output = FileOutput(chirp_tab)
                self.output_frame.layout().replaceWidget(current_widget, self.file_output)
                if clp.project['input']['mode'] == 'device':
                    chirp_tab.input_params.device_input.capture.setText('Capture Response')
            current_widget.close()
        self.mode_dropdown.currentIndexChanged.connect(update_output_mode)
        
        self.output_frame = QFrame()
        QVBoxLayout(self.output_frame)
        self.output_frame.layout().addWidget(QFrame())
        self.addWidget(self.output_frame)

        if clp.project['output']['mode'] == 'file':
            update_output_mode(0)
        else:
            update_output_mode(1)
            self.expand()


class FileOutput(QFrame):
    def __init__(self, chirp_tab):
        super().__init__()

        layout = QVBoxLayout(self)

        # amplitude - dB/Fs dropdown
        self.amplitude = CLParamNum('Amplitude', clp.project['output']['amplitude'], ['Fs', 'dBFS'], 0, 1.0, 'float')
        self.amplitude.spin_box.setDecimals(5)
        layout.addWidget(self.amplitude)
        def update_amplitude(new_value):
            if self.amplitude.units.currentIndex()==0: # FS
                clp.project['output']['amplitude'] = new_value
            else: # dBFS
                clp.project['output']['amplitude'] = 10**(new_value/20)
        self.amplitude.update_callback = update_amplitude
        def update_amplitude_units(index):
            if index==0: # FS
                self.amplitude.min = 0
                self.amplitude.max = 1.0
                self.amplitude.spin_box.setStepType(QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
                self.amplitude.set_value(clp.project['output']['amplitude'])
            else: # dBFS
                self.amplitude.min = float('-inf')
                self.amplitude.max = 0
                self.amplitude.spin_box.setStepType(QAbstractSpinBox.StepType.DefaultStepType)
                self.amplitude.set_value(20*np.log10(clp.project['output']['amplitude']))
        self.amplitude.units_update_callback = update_amplitude_units
            
        # pre padding - s/sample dropdown
        self.pre_sweep = CLParamNum('Pre Sweep', clp.project['output']['pre_sweep'], ['Sec', 'Samples'], 0, clp.MAX_ZERO_PAD, 'float')
        layout.addWidget(self.pre_sweep)
        def update_pre_sweep(new_value):
            if self.pre_sweep.units.currentIndex()==0: # sec
                clp.project['output']['pre_sweep'] = new_value
            else: # samples
                clp.project['output']['pre_sweep'] = new_value / clp.project['output']['sample_rate']
            update_output_length()
        self.pre_sweep.update_callback = update_pre_sweep
        def update_pre_sweep_units(index):
            if index==0: # sec
                self.pre_sweep.max = clp.MAX_ZERO_PAD
                self.pre_sweep.set_numtype('float')
                self.pre_sweep.set_value(clp.project['output']['pre_sweep'])
            else: # samples
                self.pre_sweep.max = clp.MAX_ZERO_PAD * clp.project['output']['sample_rate']
                self.pre_sweep.set_value(clp.project['output']['pre_sweep'] * clp.project['output']['sample_rate'])
                self.pre_sweep.set_numtype('int')
        self.pre_sweep.units_update_callback = update_pre_sweep_units
        
        # post padding - s/sample dropdown
        self.post_sweep = CLParamNum('Post Sweep', clp.project['output']['post_sweep'], ['Sec', 'Samples'], 0, clp.MAX_ZERO_PAD, 'float')
        layout.addWidget(self.post_sweep)
        def update_post_sweep(new_value):
            if self.post_sweep.units.currentIndex()==0: # sec
                clp.project['output']['post_sweep'] = new_value
            else: # samples
                clp.project['output']['post_sweep'] = new_value / clp.project['output']['sample_rate']
            update_output_length()
        self.post_sweep.update_callback = update_post_sweep
        def update_post_sweep_units(index):
            if index==0: # sec
                self.post_sweep.max = clp.MAX_ZERO_PAD
                self.post_sweep.set_numtype('float')
                self.post_sweep.set_value(clp.project['output']['post_sweep'])
            else: # samples
                self.post_sweep.max = clp.MAX_ZERO_PAD * clp.project['output']['sample_rate']
                self.post_sweep.set_value(clp.project['output']['post_sweep'] * clp.project['output']['sample_rate'])
                self.post_sweep.set_numtype('int')
        self.post_sweep.units_update_callback = update_post_sweep_units
        
        # include leading silence checkbox
        self.include_silence = QCheckBox('Include leading silence')
        self.include_silence.setChecked(clp.project['output']['include_silence'])
        layout.addWidget(self.include_silence)
        def update_include_silence(checked):
            clp.project['output']['include_silence'] = bool(checked)
            update_output_length()
        self.include_silence.stateChanged.connect(update_include_silence)
        
        # total length text box (non-interactive) - s/sample dropdown
        def calc_output_length(unit='samples'):
            sig_length = round(clp.project['output']['pre_sweep']*clp.project['output']['sample_rate'])
            sig_length += round(clp.project['chirp_length']*clp.project['output']['sample_rate'])
            sig_length += round(clp.project['output']['post_sweep']*clp.project['output']['sample_rate'])
            if clp.project['output']['include_silence']:
                sig_length *= 2
            if unit=='seconds':
                return sig_length / clp.project['output']['sample_rate']
            else:
                return sig_length
        self.output_length = CLParameter('Total stimulus length', round(calc_output_length('seconds'),2), ['Sec','Samples'])
        self.output_length.text_box.setEnabled(False)
        layout.addWidget(self.output_length)
        def update_output_length():
            if self.output_length.units.currentIndex()==0:
                self.output_length.set_value(round(calc_output_length('seconds'),2))
            else:
                self.output_length.set_value(calc_output_length('samples'))
        chirp_tab.update_output_length = update_output_length
        def update_output_length_units(index):
            update_output_length()
        self.output_length.units_update_callback = update_output_length_units
        
        # sample rate - sample rate dropdowns are very similar but have subtle differences from each other, probably don't create specific CLSampleRateDropdown
        self.sample_rate = CLParamDropdown('Sample Rate', [str(EngNumber(rate)) for rate in clp.STANDARD_SAMPLE_RATES], 'Hz', editable=True)
        def sample_rate_str2num(str_rate):
            try:
                EngNumber(str_rate) # if the input text can't be construed as a number return 0
            except:
                self.sample_rate.dropdown.setCurrentText(self.sample_rate.last_value)
                return 0
            num_rate = round(float(EngNumber(str_rate)))
            num_rate = min(max(num_rate, clp.MIN_SAMPLE_RATE), clp.MAX_SAMPLE_RATE)
            return num_rate
        if not sample_rate_str2num(str(clp.project['output']['sample_rate'])): # check if output rate in project file is valid
            clp.project['output']['sample_rate'] = 48000 # fall back to 48k
        rate_index = self.sample_rate.dropdown.findText(str(EngNumber(clp.project['output']['sample_rate'])))
        if rate_index == -1: # project output rate is non-standard
            self.sample_rate.dropdown.setCurrentText(str(EngNumber(clp.project['output']['sample_rate'])))
        else:
            self.sample_rate.dropdown.setCurrentIndex(rate_index)
        layout.addWidget(self.sample_rate)
        def update_sample_rate(index):  # fires when text is entered or when an option is selected from the dropdown.
            new_rate = sample_rate_str2num(self.sample_rate.value)
            if new_rate:
                self.sample_rate.dropdown.setCurrentText(str(EngNumber(new_rate)))
                clp.project['output']['sample_rate'] = new_rate
                update_pre_sweep_units(self.pre_sweep.units.currentIndex())
                update_post_sweep_units(self.post_sweep.units.currentIndex())
                update_output_length()
        self.sample_rate.update_callback = update_sample_rate
        
        # bit depth (dropdown - 16 int, 24 int, 32 int, 32 float)
        self.bit_depth = CLParamDropdown('Bit Depth', clp.OUTPUT_BIT_DEPTHS, '')
        depth_index = self.bit_depth.dropdown.findText(clp.project['output']['bit_depth'])
        if depth_index != -1:
            self.bit_depth.dropdown.setCurrentIndex(depth_index)
        layout.addWidget(self.bit_depth)
        def update_bit_depth(index):
            clp.project['output']['bit_depth'] = clp.OUTPUT_BIT_DEPTHS[index]
        self.bit_depth.update_callback = update_bit_depth
        
        # Number of output channels spinbox
        self.num_channels = CLParamNum('Number of channels', clp.project['output']['num_channels'],None, 1, clp.MAX_OUTPUT_CHANNELS, 'int')
        layout.addWidget(self.num_channels)
        def update_num_channels(new_value):
            clp.project['output']['num_channels'] = new_value
            
            # determine output channel before rebuilding channel dropdown list
            if clp.project['output']['channel']=='all' or clp.project['output']['channel']>clp.project['output']['num_channels']:
                channel_index = 0
            else:
                channel_index = clp.project['output']['channel']
            
            # rebuild channel dropdown list (updates trigger callback, which resets output channel to 0/'all')
            self.channel.dropdown.clear()
            self.channel.dropdown.addItem('all')
            self.channel.dropdown.addItems([str(chan) for chan in range(1, clp.project['output']['num_channels']+1)])
            
            # set correct output channel
            self.channel.dropdown.setCurrentIndex(channel_index)            
        self.num_channels.update_callback = update_num_channels
        
        # output channel dropdown
        self.channel = CLParamDropdown('Output Channel', ['all'])
        self.channel.dropdown.addItems([str(chan) for chan in range(1, clp.project['output']['num_channels']+1)])
        layout.addWidget(self.channel)
        def update_channel(index=-1, channel=None):
            if index==-1:
                if channel=='all':
                    index=0
                else:

                    if channel > clp.project['output']['num_channels']:
                        index=0
                    else:
                        index=channel
            if index==0:
                clp.project['output']['channel'] = 'all'
            else:
                clp.project['output']['channel'] = index
        self.channel.update_callback = update_channel
        update_channel(clp.project['output']['channel'])
        
        # save file button (opens browse window)
        self.output_file_button = QPushButton('Generate Chirp Stimulus File')
        layout.addWidget(self.output_file_button)
        def generate_output_file():
            save_dialog = QFileDialog()
            save_dialog.setWindowTitle('Save File')
            save_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            save_dialog.setViewMode(QFileDialog.ViewMode.Detail)
            save_dialog.setMimeTypeFilters(['audio/wav', 'application/octet-stream']) # wav files and 'all files'
            save_dialog.setDefaultSuffix('wav')
            
            if save_dialog.exec():
                output_file_path = save_dialog.selectedFiles()[0]
                generate_stimulus_file(output_file_path)
        self.output_file_button.clicked.connect(generate_output_file)


class DeviceOutput(QFrame): # much of this code is duplicated from FileOutput, but trying to DRY it out introduces a lot of weird coupling. Simpler to keep it separate
    def __init__(self, chirp_tab):
        super().__init__()

        layout = QVBoxLayout(self)
        
        # button to refresh device list, double check that current selection is valid, etc
        self.refresh = QPushButton('Refresh Device List')
        layout.addWidget(self.refresh)
        def refresh_devices():
            DeviceIO.restart_pyaudio()
            update_api(self.api.dropdown.currentIndex())
            # todo: also refresh input devices
        self.refresh.clicked.connect(refresh_devices)

        # Host API dropdown
        self.api = CLParamDropdown('Host API', DeviceIO.HOST_APIS)
        api_index = self.api.dropdown.findText(clp.project['output']['api'])
        if api_index != -1:
            self.api.dropdown.setCurrentIndex(api_index)
        else:
            clp.project['output']['api'] = self.api.dropdown.currentText()
        layout.addWidget(self.api)
        def update_api(index):
            clp.project['output']['api'] = self.api.dropdown.currentText()
            
            self.device.dropdown.blockSignals(True)
            self.device.dropdown.clear()
            self.device.dropdown.addItems(DeviceIO.get_device_names('output', clp.project['output']['api']))
            self.device.dropdown.blockSignals(False)
            set_device_index(clp.project['output']['device'])
            update_device(self.device.dropdown.currentIndex()) # force callback to run in case device name is the same across APIs
        self.api.update_callback = update_api

        # Device selection
        self.device = CLParamDropdown('Output Device', DeviceIO.get_device_names('output', clp.project['output']['api']))
        def set_device_index(device_name):
            index = self.device.dropdown.findText(device_name) # find device name in device list
            if index == -1: # device name not given or not found, use default device
                default_device = DeviceIO.get_default_output_device(clp.project['output']['api'])
                index = self.device.dropdown.findText(default_device)
            self.device.dropdown.setCurrentIndex(index)
        set_device_index(clp.project['output']['device'])
        clp.project['output']['device'] = self.device.dropdown.currentText()
        clp.project['output']['num_channels'] = DeviceIO.get_num_output_channels(clp.project['output']['device'], clp.project['output']['api'])
        layout.addWidget(self.device)
        def update_device(index):
            set_device_index(self.device.dropdown.currentText())
            clp.project['output']['device'] = self.device.dropdown.currentText()

            self.sample_rate.dropdown.blockSignals(True)
            self.sample_rate.dropdown.clear()
            self.sample_rate.dropdown.addItems([str(EngNumber(rate)) for rate in DeviceIO.get_valid_standard_sample_rates(clp.project['output']['device'], clp.project['output']['api'])])
            update_sample_rate(new_rate=clp.project['output']['sample_rate'])
            self.sample_rate.dropdown.blockSignals(False)

            set_num_channels(DeviceIO.get_num_output_channels(clp.project['output']['device'], clp.project['output']['api']))
            update_channel(channel=clp.project['output']['channel'])
        self.device.update_callback = update_device

        # amplitude - dB/Fs dropdown
        self.amplitude = CLParamNum('Amplitude', clp.project['output']['amplitude'], ['Fs', 'dBFS'], 0, 1.0, 'float')
        self.amplitude.spin_box.setDecimals(5)
        layout.addWidget(self.amplitude)
        def update_amplitude(new_value):
            if self.amplitude.units.currentIndex()==0: # FS
                clp.project['output']['amplitude'] = new_value
            else: # dBFS
                clp.project['output']['amplitude'] = 10**(new_value/20)
        self.amplitude.update_callback = update_amplitude
        def update_amplitude_units(index):
            if index==0: # FS
                self.amplitude.min = 0
                self.amplitude.max = 1.0
                self.amplitude.spin_box.setStepType(QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
                self.amplitude.set_value(clp.project['output']['amplitude'])
            else: # dBFS
                self.amplitude.min = float('-inf')
                self.amplitude.max = 0
                self.amplitude.spin_box.setStepType(QAbstractSpinBox.StepType.DefaultStepType)
                self.amplitude.set_value(20*np.log10(clp.project['output']['amplitude']))
        self.amplitude.units_update_callback = update_amplitude_units
            
        # pre padding - s/sample dropdown
        self.pre_sweep = CLParamNum('Pre Sweep', clp.project['output']['pre_sweep'], ['Sec', 'Samples'], 0, clp.MAX_ZERO_PAD, 'float')
        layout.addWidget(self.pre_sweep)
        def update_pre_sweep(new_value):
            if self.pre_sweep.units.currentIndex()==0: # sec
                clp.project['output']['pre_sweep'] = new_value
            else: # samples
                clp.project['output']['pre_sweep'] = new_value / clp.project['output']['sample_rate']
            update_output_length()
        self.pre_sweep.update_callback = update_pre_sweep
        def update_pre_sweep_units(index):
            if index==0: # sec
                self.pre_sweep.max = clp.MAX_ZERO_PAD
                self.pre_sweep.set_numtype('float')
                self.pre_sweep.set_value(clp.project['output']['pre_sweep'])
            else: # samples
                self.pre_sweep.max = clp.MAX_ZERO_PAD * clp.project['output']['sample_rate']
                self.pre_sweep.set_value(clp.project['output']['pre_sweep'] * clp.project['output']['sample_rate'])
                self.pre_sweep.set_numtype('int')
        self.pre_sweep.units_update_callback = update_pre_sweep_units
        
        # post padding - s/sample dropdown
        self.post_sweep = CLParamNum('Post Sweep', clp.project['output']['post_sweep'], ['Sec', 'Samples'], 0, clp.MAX_ZERO_PAD, 'float')
        layout.addWidget(self.post_sweep)
        def update_post_sweep(new_value):
            if self.post_sweep.units.currentIndex()==0: # sec
                clp.project['output']['post_sweep'] = new_value
            else: # samples
                clp.project['output']['post_sweep'] = new_value / clp.project['output']['sample_rate']
            update_output_length()
        self.post_sweep.update_callback = update_post_sweep
        def update_post_sweep_units(index):
            if index==0: # sec
                self.post_sweep.max = clp.MAX_ZERO_PAD
                self.post_sweep.set_numtype('float')
                self.post_sweep.set_value(clp.project['output']['post_sweep'])
            else: # samples
                self.post_sweep.max = clp.MAX_ZERO_PAD * clp.project['output']['sample_rate']
                self.post_sweep.set_value(clp.project['output']['post_sweep'] * clp.project['output']['sample_rate'])
                self.post_sweep.set_numtype('int')
        self.post_sweep.units_update_callback = update_post_sweep_units
        
        # include leading silence checkbox
        self.include_silence = QCheckBox('Include leading silence')
        self.include_silence.setChecked(clp.project['output']['include_silence'])
        layout.addWidget(self.include_silence)
        def update_include_silence(checked):
            clp.project['output']['include_silence'] = bool(checked)
            update_output_length()
            if clp.project['input']['mode'] == 'device' and clp.project['input']['use_output_length']:
                chirp_tab.input_params.device_input.update_auto_length(True)
        self.include_silence.stateChanged.connect(update_include_silence)
        
        # total length text box (non-interactive) - s/sample dropdown
        def calc_output_length(unit='samples'):
            sig_length = round(clp.project['output']['pre_sweep']*clp.project['output']['sample_rate'])
            sig_length += round(clp.project['chirp_length']*clp.project['output']['sample_rate'])
            sig_length += round(clp.project['output']['post_sweep']*clp.project['output']['sample_rate'])
            if clp.project['output']['include_silence']:
                sig_length *= 2
            if unit=='seconds':
                return sig_length / clp.project['output']['sample_rate']
            else:
                return sig_length
        self.output_length = CLParameter('Total stimulus length', round(calc_output_length('seconds'),2), ['Sec','Samples'])
        self.output_length.text_box.setEnabled(False)
        layout.addWidget(self.output_length)
        def update_output_length():
            if self.output_length.units.currentIndex()==0:
                self.output_length.set_value(round(calc_output_length('seconds'),2))
            else:
                self.output_length.set_value(calc_output_length('samples'))
        chirp_tab.update_output_length = update_output_length
        def update_output_length_units(index):
            update_output_length()
        self.output_length.units_update_callback = update_output_length_units
        
        # sample rate
        self.sample_rate = CLParamDropdown('Sample Rate', [str(EngNumber(rate)) for rate in DeviceIO.get_valid_standard_sample_rates(clp.project['output']['device'], clp.project['output']['api'])], 'Hz', editable=True)
        layout.addWidget(self.sample_rate)
        def update_sample_rate(index=-1, new_rate=0):  # fires when text is entered or when an option is selected from the dropdown.
            if not new_rate:
                new_rate = sample_rate_str2num(self.sample_rate.value)
            if new_rate:
                if DeviceIO.is_sample_rate_valid(new_rate, clp.project['output']['device'], clp.project['output']['api']):
                    self.sample_rate.dropdown.setCurrentText(str(EngNumber(new_rate)))
                else:
                    # find the closest supported sample rate to new_rate
                    standard_rates = [self.sample_rate.dropdown.itemText(i) for i in range(self.sample_rate.dropdown.count())]
                    deltas = [abs(sample_rate_str2num(standard_rate) - new_rate) for standard_rate in standard_rates]
                    self.sample_rate.dropdown.setCurrentIndex(deltas.index(min(deltas)))
                    new_rate = sample_rate_str2num(self.sample_rate.dropdown.currentText())
                clp.project['output']['sample_rate'] = new_rate
                self.sample_rate.value = new_rate # set manually because calling externally with new_rate skips CLParamDropdown callback
                self.sample_rate.last_value = new_rate
                update_pre_sweep_units(self.pre_sweep.units.currentIndex())
                update_post_sweep_units(self.post_sweep.units.currentIndex())
                update_output_length()
            else:
                self.sample_rate.dropdown.setCurrentText(self.sample_rate.last_value)
                self.sample_rate.value = self.sample_rate.last_value
        self.sample_rate.update_callback = update_sample_rate
        update_sample_rate(new_rate=clp.project['output']['sample_rate'])
        def sample_rate_str2num(str_rate):
            try:
                EngNumber(str_rate) # if the input text can't be construed as a number return 0
            except:
                self.sample_rate.dropdown.setCurrentText(self.sample_rate.last_value)
                return 0
            num_rate = round(float(EngNumber(str_rate)))
            num_rate = min(max(num_rate, clp.MIN_SAMPLE_RATE), clp.MAX_SAMPLE_RATE)
            return num_rate

        # no control over bit depth, use float32 for everything. I suspect PortAudio silently converts formats internally so there isn't any point in even displaying it

        # output channel
        self.channel = CLParamDropdown('Output Channel', ['all'])
        def set_num_channels(num_channels):
            clp.project['output']['num_channels'] = num_channels
            self.channel.dropdown.blockSignals(True)
            self.channel.dropdown.clear()
            self.channel.dropdown.addItem('all')
            self.channel.dropdown.addItems([str(chan) for chan in range(1, num_channels+1)])
            self.channel.dropdown.blockSignals(False)
        set_num_channels(clp.project['output']['num_channels'])
        layout.addWidget(self.channel)
        def update_channel(index=-1, channel=None):
            if index==-1:
                if channel=='all':
                    index=0
                else:
                    if channel > clp.project['output']['num_channels']:
                        index=0
                    else:
                        index=channel
                self.channel.dropdown.setCurrentIndex(index)
            if index==0:
                clp.project['output']['channel'] = 'all'
            else:
                clp.project['output']['channel'] = index
        self.channel.update_callback = update_channel
        update_channel(channel=clp.project['output']['channel'])

        # play button
        self.play = QPushButton('Play Stimulus')
        # gray out and change text if current selected device seems to be invalid
        layout.addWidget(self.play)
        self.play_start_time = time()
        def play_stimulus():
            stimulus = generate_output_stimulus()
            DeviceIO.play(stimulus, clp.project['output']['sample_rate'], clp.project['output']['device'], clp.project['output']['api'], active_callback=while_playing, finished_callback=when_play_finished)
            self.play_start_time = time()
            chirp_tab.output_params.setEnabled(False)
            if clp.project['input']['mode'] == 'device':
                chirp_tab.input_params.setEnabled(False)
        self.play.clicked.connect(play_stimulus)
        self.play_stimulus = play_stimulus
        def while_playing():
            self.play.setText('Playing: ' + str(round(time()-self.play_start_time, 2)) + ' / ' + self.output_length.value)
        def when_play_finished():
            self.play.setText('Play Stimulus')
            chirp_tab.output_params.setEnabled(True)
            if clp.project['input']['mode'] == 'device':
                chirp_tab.input_params.setEnabled(True)


class InputParameters(QCollapsible):
    def __init__(self, chirp_tab):
        super().__init__('Input')

        self.mode_dropdown = QComboBox()
        self.addWidget(self.mode_dropdown)
        self.mode_dropdown.addItems(['File', 'Device'])
        def update_input_mode(index):
            clp.IO['input']['length_samples'] = 0
            clp.IO['input']['sample_rate'] = 0
            clp.IO['input']['channels'] = 0
            clp.IO['input']['numtype'] = 0
            
            current_widget = self.input_frame.layout().itemAt(0).widget()
            if index:
                clp.project['input']['mode'] = 'device'
                self.device_input = DeviceInput(chirp_tab)
                self.input_frame.layout().replaceWidget(current_widget, self.device_input)
            else:
                clp.project['input']['mode'] = 'file'
                self.file_input = FileInput(chirp_tab)
                self.input_frame.layout().replaceWidget(current_widget, self.file_input)
            current_widget.close()
        self.mode_dropdown.currentIndexChanged.connect(update_input_mode)

        self.input_frame = QFrame()
        QVBoxLayout(self.input_frame)
        self.input_frame.layout().addWidget(QFrame())
        self.addWidget(self.input_frame)

        if clp.project['input']['mode'] == 'file':
            update_input_mode(0)
        else:
            update_input_mode(1)


        # calibration parameters section
        self.cal_params = QCollapsible('Calibration')
        self.addWidget(self.cal_params)

        self.FS_per_Pa = CLParamNum('Acoustic', clp.project['FS_per_Pa'], 'FS/Pa', numtype='float') # todo: set reasonable minimum (also set in calibration dialog)
        self.FS_per_Pa.spin_box.setDecimals(6)
        self.cal_params.addWidget(self.FS_per_Pa)
        def update_FS_per_Pa(new_val):
            clp.project['FS_per_Pa'] = new_val
            chirp_tab.analyze()
        self.FS_per_Pa.update_callback = update_FS_per_Pa
        
        self.FS_per_V = CLParamNum('Electrical', clp.project['FS_per_V'], 'FS/V', numtype='float') # todo: set reasonable minimum
        self.FS_per_V.spin_box.setDecimals(6)
        self.cal_params.addWidget(self.FS_per_V)
        def update_FS_per_V(new_val):
            clp.project['FS_per_V'] = new_val
            chirp_tab.analyze()
        self.FS_per_V.update_callback = update_FS_per_V

        self.cal_button = QPushButton('Calibrate...')
        self.cal_params.addWidget(self.cal_button)
        def open_cal_dialog():
            cal_dialog = CalibrationDialog(chirp_tab)
            if cal_dialog.exec():
                chirp_tab.analyze()
        self.cal_button.clicked.connect(open_cal_dialog)


        self.expand()

        
class FileInput(QFrame):
    def __init__(self, chirp_tab):
        super().__init__()

        layout = QVBoxLayout(self)

        self.file = CLParamFile('Input File', clp.project['input']['file'])
        self.file.mime_types = ['audio/wav', 'application/octet-stream']
        layout.addWidget(self.file)
        def update_file(file_path=None):

            if not file_path:
                file_path = self.file.value
            try:
                clp.project['input']['file'] = file_path

                # read input file to signals
                clp.signals['raw_response'] = read_audio_file(file_path)

                file_info = audio_file_info(file_path)

                clp.IO['input']['length_samples'] = file_info['length_samples']
                clp.IO['input']['sample_rate'] = file_info['sample_rate']
                clp.IO['input']['channels'] = file_info['channels']
                clp.IO['input']['numtype'] = file_info['numtype']
                
                update_input_length_units(self.input_length.units.currentIndex())
                self.sample_rate.set_value(str(EngNumber(file_info['sample_rate'])))
                self.num_channels.set_value(file_info['channels'])
                update_num_channels(file_info['channels'])
                self.channel.setEnabled(True)
                self.bit_depth.set_value(file_info['numtype'])
                
                if clp.project['use_input_rate']:
                    if clp.project['sample_rate'] != clp.IO['input']['sample_rate']:
                        chirp_tab.update_sample_rate(new_rate=clp.IO['input']['sample_rate'])
                
                self.file.text_box.setStyleSheet('')
                
            except FileNotFoundError:
                clp.IO['input']['length_samples'] = 0
                clp.IO['input']['sample_rate'] = 0
                clp.IO['input']['channels'] = 0
                clp.IO['input']['numtype'] = ''
                
                self.input_length.set_value('file not found')
                self.sample_rate.set_value('')
                self.num_channels.set_value('')
                self.channel.setEnabled(False)
                self.bit_depth.set_value('')
                
                self.file.text_box.setStyleSheet('QLineEdit { background-color: orange; }')
        #chirp_tab.update_input_file = update_file
        self.file.update_callback = update_file
        self.update_input_file = update_file # make inner function callable as a method
        
        # input length
        self.input_length = CLParameter('Input file length', 0, ['Sec','Samples'])
        self.input_length.text_box.setEnabled(False)
        layout.addWidget(self.input_length)
        def update_input_length_units(index):
            if clp.IO['input']['length_samples']:
                if index: # samples
                    self.input_length.set_value(clp.IO['input']['length_samples'])
                else: # seconds
                    self.input_length.set_value(round(clp.IO['input']['length_samples'] / clp.IO['input']['sample_rate'],2))
        self.input_length.units_update_callback = update_input_length_units
        
        # input sample rate
        self.sample_rate = CLParameter('Sample rate', 0, 'Hz')
        self.sample_rate.text_box.setEnabled(False)
        layout.addWidget(self.sample_rate)
        
        # input bit depth
        self.bit_depth = CLParameter('Number format', '')
        self.bit_depth.text_box.setEnabled(False)
        layout.addWidget(self.bit_depth)
        
        # number of input channels
        self.num_channels = CLParameter('Number of channels', 0)
        self.num_channels.text_box.setEnabled(False)
        layout.addWidget(self.num_channels)
        def update_num_channels(new_value):
            # determine input channel before rebuilding channel dropdown list
            if clp.project['input']['channel']>clp.IO['input']['channels']:
                channel_index = 0
                clp.project['input']['channel'] = 1
            else:
                channel_index = clp.project['input']['channel'] - 1
            
            # rebuild channel dropdown list (updates trigger callback, which resets output channel to 0/'all')
            self.channel.dropdown.clear()
            self.channel.dropdown.addItems([str(chan) for chan in range(1, clp.IO['input']['channels']+1)])
            
            # set correct output channel
            self.channel.dropdown.setCurrentIndex(channel_index)            
        self.num_channels.update_callback = update_num_channels
        
        # input channel dropdown        
        self.channel = CLParamDropdown('Channel', ['1'])
        layout.addWidget(self.channel)
        def update_channel(index):
            clp.project['input']['channel'] = index + 1
        self.channel.update_callback = update_channel
        
        # prepopulate input file info
        update_file(clp.project['input']['file'])
        
        self.analyze_button = QPushButton('Analyze')
        layout.addWidget(self.analyze_button)
        self.analyze_button.clicked.connect(chirp_tab.analyze)


class DeviceInput(QFrame):
    def __init__(self, chirp_tab):
        super().__init__()

        layout = QVBoxLayout(self)
        
        # button to refresh device list, double check that current selection is valid, etc
        self.refresh = QPushButton('Refresh Device List')
        layout.addWidget(self.refresh)
        def refresh_devices():
            DeviceIO.restart_pyaudio()
            update_api(self.api.dropdown.currentIndex())
            # todo: also refresh output devices
        self.refresh.clicked.connect(refresh_devices)

        # Host API dropdown
        self.api = CLParamDropdown('Host API', DeviceIO.HOST_APIS)
        api_index = self.api.dropdown.findText(clp.project['input']['api'])
        if api_index != -1:
            self.api.dropdown.setCurrentIndex(api_index)
        else:
            clp.project['input']['api'] = self.api.dropdown.currentText()
        layout.addWidget(self.api)
        def update_api(index):
            clp.project['input']['api'] = self.api.dropdown.currentText()
            
            self.device.dropdown.blockSignals(True)
            self.device.dropdown.clear()
            self.device.dropdown.addItems(DeviceIO.get_device_names('input', clp.project['input']['api']))
            self.device.dropdown.blockSignals(False)
            set_device_index(clp.project['input']['device'])
            update_device(self.device.dropdown.currentIndex()) # force callback to run in case device name is the same across APIs
        self.api.update_callback = update_api

        # Device selection
        self.device = CLParamDropdown('Input Device', DeviceIO.get_device_names('input', clp.project['input']['api']))
        def set_device_index(device_name):
            index = self.device.dropdown.findText(device_name) # find device name in device list
            if index == -1: # device name not given or not found, use default device
                default_device = DeviceIO.get_default_input_device(clp.project['input']['api'])
                index = self.device.dropdown.findText(default_device)
            self.device.dropdown.setCurrentIndex(index)
        set_device_index(clp.project['input']['device'])
        clp.project['input']['device'] = self.device.dropdown.currentText()
        layout.addWidget(self.device)
        def update_device(index):
            set_device_index(self.device.dropdown.currentText())
            clp.project['input']['device'] = self.device.dropdown.currentText()

            self.sample_rate.dropdown.blockSignals(True)
            self.sample_rate.dropdown.clear()
            self.sample_rate.dropdown.addItems([str(EngNumber(rate)) for rate in DeviceIO.get_valid_standard_sample_rates(clp.project['input']['device'], clp.project['input']['api'])])
            update_sample_rate(new_rate=clp.project['input']['sample_rate'])
            self.sample_rate.dropdown.blockSignals(False)

            set_num_channels(DeviceIO.get_num_input_channels(clp.project['input']['device'], clp.project['input']['api']))
            update_channel(channel=clp.project['input']['channel'])

            clp.IO['input']['length_samples'] = 0
            clp.IO['input']['sample_rate'] = 0
            clp.IO['input']['channels'] = 0
            clp.IO['input']['numtype'] = 0
            clp.signals['raw_response'] = []
            self.save.setEnabled(False)

        self.device.update_callback = update_device
        
        # auto capture length checkbox
        self.auto_length = QCheckBox('auto')
        self.auto_length.setChecked(clp.project['input']['use_output_length'])
        layout.addWidget(self.auto_length)
        def update_auto_length(checked):
            clp.project['input']['use_output_length'] = checked
            self.capture_length.spin_box.setEnabled(not checked)
            if checked:
                clp.project['input']['capture_length'] = calc_output_length('seconds')
                update_capture_length_units(self.capture_length.units.currentIndex())
        self.auto_length.stateChanged.connect(update_auto_length)
        def calc_output_length(unit='samples'):
            sig_length = round(clp.project['output']['pre_sweep']*clp.project['output']['sample_rate'])
            sig_length += round(clp.project['chirp_length']*clp.project['output']['sample_rate'])
            sig_length += round(clp.project['output']['post_sweep']*clp.project['output']['sample_rate'])
            if clp.project['output']['include_silence']:
                sig_length *= 2
            if unit=='seconds':
                return sig_length / clp.project['output']['sample_rate']
            else:
                return sig_length
        
        # total length spinbox - s/sample dropdown
        self.capture_length = CLParamNum('Capture length', round(clp.project['input']['capture_length'],2), ['Sec','Samples'], 0, 2*(clp.MAX_CHIRP_LENGTH+2*clp.MAX_ZERO_PAD), 'float')
        layout.addWidget(self.capture_length)
        def update_capture_length(new_value):
            if self.capture_length.units.currentIndex()==1: # seconds
                new_value = new_value / clp.project['input']['sample_rate']
            clp.project['input']['capture_length'] = new_value
        self.capture_length.update_callback = update_capture_length
        chirp_tab.update_capture_length = update_capture_length
        def update_capture_length_units(index):
            if index==0: # seconds
                self.capture_length.set_numtype('float')
                self.capture_length.max = 2*(clp.MAX_CHIRP_LENGTH+2*clp.MAX_ZERO_PAD)
                self.capture_length.set_value(clp.project['input']['capture_length'])
            else: # samples
                self.capture_length.max = round(2*(clp.MAX_CHIRP_LENGTH+2*clp.MAX_ZERO_PAD) * clp.project['input']['sample_rate'])
                self.capture_length.set_numtype('int')
                self.capture_length.set_value(round(clp.project['input']['capture_length'] * clp.project['input']['sample_rate']))
        self.capture_length.units_update_callback = update_capture_length_units
        update_auto_length(clp.project['input']['use_output_length'])
        self.update_auto_length = update_auto_length
        
        # sample rate
        self.sample_rate = CLParamDropdown('Sample Rate', [str(EngNumber(rate)) for rate in DeviceIO.get_valid_standard_sample_rates(clp.project['input']['device'], clp.project['input']['api'])], 'Hz', editable=True)
        layout.addWidget(self.sample_rate)
        def update_sample_rate(index=-1, new_rate=0):  # fires when text is entered or when an option is selected from the dropdown.
            if not new_rate:
                new_rate = sample_rate_str2num(self.sample_rate.value)
            if new_rate:
                if DeviceIO.is_sample_rate_valid(new_rate, clp.project['input']['device'], clp.project['input']['api']):
                    self.sample_rate.dropdown.setCurrentText(str(EngNumber(new_rate)))
                else:
                    # find the closest supported sample rate to new_rate
                    standard_rates = [self.sample_rate.dropdown.itemText(i) for i in range(self.sample_rate.dropdown.count())]
                    deltas = [abs(sample_rate_str2num(standard_rate) - new_rate) for standard_rate in standard_rates]
                    self.sample_rate.dropdown.setCurrentIndex(deltas.index(min(deltas)))
                    new_rate = sample_rate_str2num(self.sample_rate.dropdown.currentText())
                clp.project['input']['sample_rate'] = new_rate
                self.sample_rate.value = new_rate # set manually because calling externally with new_rate skips CLParamDropdown callback
                self.sample_rate.last_value = new_rate
                update_capture_length_units(self.capture_length.units.currentIndex())
            else:
                self.sample_rate.dropdown.setCurrentText(self.sample_rate.last_value)
                self.sample_rate.value = self.sample_rate.last_value
        self.sample_rate.update_callback = update_sample_rate
        update_sample_rate(new_rate=clp.project['input']['sample_rate'])
        def sample_rate_str2num(str_rate):
            try:
                EngNumber(str_rate) # if the input text can't be construed as a number return 0
            except:
                self.sample_rate.dropdown.setCurrentText(self.sample_rate.last_value)
                return 0
            num_rate = round(float(EngNumber(str_rate)))
            num_rate = min(max(num_rate, clp.MIN_SAMPLE_RATE), clp.MAX_SAMPLE_RATE)
            return num_rate

        # no control over bit depth, use float32 for everything. I suspect PortAudio silently converts formats internally so there isn't any point in even displaying it

        # input channel
        self.channel = CLParamDropdown('Input Channel', [str(0)])
        def set_num_channels(num_channels):
            clp.IO['input']['channels'] = num_channels
            self.channel.dropdown.blockSignals(True)
            self.channel.dropdown.clear()
            self.channel.dropdown.addItems([str(chan) for chan in range(1, num_channels+1)])
            self.channel.dropdown.blockSignals(False)
        set_num_channels(DeviceIO.get_num_input_channels(clp.project['input']['device'], clp.project['input']['api']))
        layout.addWidget(self.channel)
        def update_channel(index=-1, channel=None):
            if index==-1:
                if channel > clp.IO['input']['channels']:
                    index=0
                else:
                    index=channel-1
                self.channel.dropdown.setCurrentIndex(index)
            clp.project['input']['channel'] = index+1
            
            if clp.IO['input']['length_samples']:
                chirp_tab.analyze()
        self.channel.update_callback = update_channel
        update_channel(channel=clp.project['input']['channel'])

        # capture button - todo: is "record" or "acquire" more intuitive?
        # todo: gray out and change text if current selected device seems to be invalid
        if clp.project['output']['mode'] == 'device':
            button_text = 'Play and Capture'
        else:
            button_text = 'Capture Response'
        self.capture = QPushButton(button_text)
        layout.addWidget(self.capture)
        self.capture_start_time = time()
        def capture_response():
            DeviceIO.record(round(clp.project['input']['capture_length']*clp.project['input']['sample_rate']), clp.project['input']['sample_rate'], clp.project['input']['device'], clp.project['input']['api'], active_callback=while_capturing, finished_callback=capture_receiver.capture_finished.emit)
            self.capture_start_time = time()
            chirp_tab.input_params.setEnabled(False)
            if clp.project['output']['mode'] == 'device':
                chirp_tab.output_params.device_output.play_stimulus()
        self.capture.clicked.connect(capture_response)
        def while_capturing():
            self.capture.setText('Capturing: ' + str(round(time()-self.capture_start_time, 2)) + ' / ' + str(self.capture_length.value))
        
        @Slot(np.ndarray)
        def when_capture_finished(captured_response):
            if clp.project['output']['mode'] == 'device':
                self.capture.setText('Play and Capture')
            else:
                self.capture.setText('Capture Response')

            chirp_tab.input_params.setEnabled(True) # todo: handle corner cases where capture length is significantly shorter than stimulus length
            if clp.project['output']['mode'] == 'device':
                chirp_tab.output_params.setEnabled(True)

            clp.IO['input']['length_samples'] = len(captured_response)
            clp.IO['input']['sample_rate'] = clp.project['input']['sample_rate']
            clp.IO['input']['channels'] = np.shape(captured_response)[1]
            clp.IO['input']['numtype'] = '32 float'

            clp.signals['raw_response'] = captured_response

            if clp.project['use_input_rate']:
                    if clp.project['sample_rate'] != clp.IO['input']['sample_rate']:
                        chirp_tab.update_sample_rate(new_rate=clp.IO['input']['sample_rate'])
            chirp_tab.analyze()

            self.save.setEnabled(True)
        
        # need to go through signal and slot to actually get data from PyAudio thread back into Qt thread
        # in order to work a signal must be a member of an instance of QObject. todo: figure out if there is a simpler/cleaner way (creating signal in DeviceInput.__init__() and calling .connect outside of DeviceInput doesn't seem to work)
        class CaptureReceiver(QObject):
            capture_finished = Signal(np.ndarray) 
        capture_receiver = CaptureReceiver()
        capture_receiver.capture_finished.connect(when_capture_finished)
        
        # save last capture button
        self.save = QPushButton('Save Last Capture')
        self.save.setEnabled(False)
        layout.addWidget(self.save)
        def save_capture():
            if clp.IO['input']['length_samples']:
                save_dialog = QFileDialog()
                save_dialog.setWindowTitle('Save File')
                save_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
                save_dialog.setViewMode(QFileDialog.ViewMode.Detail)
                save_dialog.setNameFilters(['WAV audio (24-bit) (*.wav)', 'WAV audio (16-bit) (*.wav)', 'WAV audio (32-bit Int) (*.wav)', 'WAV audio (32-bit Float) (*.wav)', 'All files (*)']) # todo: this feels a little kludgy, see if there is a simple alternative without adding UI elements to DeviceInput or recreating QFileDialog from scratch...
                save_dialog.setDefaultSuffix('wav')
                bit_depth = '24 int'
                def filterSelected(filter_string):
                    nonlocal bit_depth
                    if '16-bit' in filter_string:
                        bit_depth = '16 int'
                    elif '32-bit Int' in filter_string:
                        bit_depth = '32 int'
                    elif '32-bit Float' in filter_string:
                        bit_depth = '32 float'
                    else:
                        bit_depth = '24 int'
                    default_suffix = filter_string.split('(*')[1].split(')')[0]
                    save_dialog.setDefaultSuffix(default_suffix)
                save_dialog.filterSelected.connect(filterSelected)
                
                if save_dialog.exec():
                    output_file_path = save_dialog.selectedFiles()[0]
                    write_audio_file(clp.signals['raw_response'], output_file_path, clp.IO['input']['sample_rate'],bit_depth)
            else:
                self.save.setEnabled(False) # disable button if it is accidentally left enabled after raw response is cleared
        self.save.clicked.connect(save_capture)
