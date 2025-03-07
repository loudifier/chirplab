import CLProject as clp
from CLGui import CLTab, CLParameter, CLParamNum, CLParamDropdown, CLParamFile, QCollapsible, QHSeparator
from CLAnalysis import generate_stimulus, read_response, generate_stimulus_file, audio_file_info
import numpy as np
from qtpy.QtWidgets import QPushButton, QCheckBox, QAbstractSpinBox, QFileDialog, QComboBox, QFrame, QStackedWidget, QVBoxLayout, QSizePolicy
import pyqtgraph as pg
from engineering_notation import EngNumber
import DeviceIO


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
        # first, check if input file is valid
        self.update_input_file()
        
        # if input file was found read it in, otherwise blank out response
        if clp.IO['input']['length_samples']:
            read_response() # reads in raw response, gets desired channel, and puts segment containing chirp in clp.signals['stimulus']
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
        def sample_rate_str2num(new_value):
            if 'input' in new_value:
               self.sample_rate.last_value = 'use input rate'
               self.sample_rate.dropdown.setCurrentIndex(0)
               return clp.IO['input']['sample_rate']
            try:
                EngNumber(new_value) # if the input text can't be construed as a number then revert and return 0
            except:
                self.sample_rate.dropdown.setCurrentText(self.sample_rate.last_value)
                return 0
            new_rate = round(float(EngNumber(new_value)))
            new_rate = min(max(new_rate, clp.MIN_SAMPLE_RATE), clp.MAX_SAMPLE_RATE)
            self.sample_rate.last_value = str(EngNumber(new_rate))
            self.sample_rate.dropdown.setCurrentText(str(EngNumber(new_rate))) # todo: handle corner case where this can fire recalculation when clicking the dropdown after typing in a sample rate 
            return new_rate
        
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
            if index:
                clp.project['output']['mode'] = 'device'
                # todo: add device output refresh
            else:
                clp.project['output']['mode'] = 'file'
                self.file_output.refresh()
            self.output_stack.setCurrentIndex(index)
        self.mode_dropdown.currentIndexChanged.connect(update_output_mode)
        
        self.output_stack = ResizableStackedWidget()
        self.addWidget(self.output_stack)

        self.file_output = FileOutput(chirp_tab)
        self.output_stack.addWidget(self.file_output)

        self.device_output = DeviceOutput(chirp_tab)
        self.output_stack.addWidget(self.device_output)

        if clp.project['output']['mode'] == 'device':
            self.mode_dropdown.setCurrentIndex(1)
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
        
        # sample rate
        self.sample_rate = CLParamDropdown('Sample Rate', [str(EngNumber(rate)) for rate in clp.STANDARD_SAMPLE_RATES], 'Hz')
        rate_index = self.sample_rate.dropdown.findText(str(EngNumber(clp.project['output']['sample_rate'])))
        if rate_index != -1:
            self.sample_rate.dropdown.setCurrentIndex(rate_index)
        layout.addWidget(self.sample_rate)
        def update_sample_rate(index):
            clp.project['output']['sample_rate'] = clp.STANDARD_SAMPLE_RATES[index]
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
        def update_channel(index):
            if index==0:
                clp.project['output']['channel'] = 'all'
            else:
                clp.project['output']['channel'] = index
        self.channel.update_callback = update_channel
        
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

    def refresh(self): # call to update output parameters that may have changed elsewhere, like in the DeviceOutput settings
        self.amplitude.units_update_callback(self.amplitude.units.currentIndex())


class DeviceOutput(QFrame): # much of this code is duplicated from FileOutput, but trying to DRY it out introduces a lot of weird coupling. Simpler to keep it separate and add refresh() method to sync changes
    def __init__(self, chirp_tab):
        super().__init__()

        layout = QVBoxLayout(self)
        
        # button to refresh device list, double check that current selection is valid, etc
        self.refresh = QPushButton('Refresh Device List')
        layout.addWidget(self.refresh)

        # Host API dropdown
        self.api = CLParamDropdown('Host API', DeviceIO.HOST_APIS)
        api_index = self.api.dropdown.findText(clp.project['output']['api'])
        if api_index != -1:
            self.api.dropdown.setCurrentIndex(api_index)
        else:
            clp.project['output']['api'] = self.api.dropdown.currentText()
        layout.addWidget(self.api)

        # Device selection
        self.device = CLParamDropdown('Output Device', DeviceIO.get_device_names('output', clp.project['output']['api']))
        layout.addWidget(self.device)
        def update_device(index):
            print(DeviceIO.device_name_to_index(self.device.dropdown.currentText(), clp.project['output']['api']))
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
        self.sample_rate = CLParamDropdown('Sample Rate', [str(EngNumber(rate)) for rate in clp.STANDARD_SAMPLE_RATES], 'Hz')
        rate_index = self.sample_rate.dropdown.findText(str(EngNumber(clp.project['output']['sample_rate'])))
        if rate_index != -1:
            self.sample_rate.dropdown.setCurrentIndex(rate_index)
        layout.addWidget(self.sample_rate)
        def update_sample_rate(index):
            clp.project['output']['sample_rate'] = clp.STANDARD_SAMPLE_RATES[index]
            update_pre_sweep_units(self.pre_sweep.units.currentIndex())
            update_post_sweep_units(self.post_sweep.units.currentIndex())
            update_output_length()
        self.sample_rate.update_callback = update_sample_rate

        # no control over bit depth, always use default format for device

        # output channel
        self.channel = CLParamDropdown('Output Channel', ['1'])
        layout.addWidget(self.channel)

        # play button
        self.play = QPushButton('Play Stimulus')
        layout.addWidget(self.play)
        # gray out and change text if current selected device seems to be invalid



class InputParameters(QCollapsible):
    def __init__(self, chirp_tab):
        super().__init__('Input')

        self.mode_dropdown = QComboBox()
        #self.addWidget(self.mode_dropdown)
        self.mode_dropdown.addItems(['File', 'Device'])
        def update_input_mode(index):
            self.input_stack.setCurrentIndex(index)
        self.mode_dropdown.activated.connect(update_input_mode)

        self.input_stack = ResizableStackedWidget()
        self.addWidget(self.input_stack)

        self.file_input = FileInput(chirp_tab)
        self.input_stack.addWidget(self.file_input)

        self.device_input = DeviceInput(chirp_tab)
        self.input_stack.addWidget(self.device_input) 

        self.expand()

        
class FileInput(QFrame): # todo: clean up object names that are now redundant after separating chirp tab panel into separate classes. e.g. `file_output.output_amplitude` -> `file_output.amplitude`
    def __init__(self, chirp_tab):
        super().__init__()

        layout = QVBoxLayout(self)

        self.input_file = CLParamFile('Input File', clp.project['input']['file'])
        self.input_file.mime_types = ['audio/wav', 'application/octet-stream']
        layout.addWidget(self.input_file)
        def update_input_file(file_path=None):
            if not file_path:
                file_path = self.input_file.value
            try:
                input_file_info = audio_file_info(file_path)
                
                clp.project['input']['file'] = file_path
                
                clp.IO['input']['length_samples'] = input_file_info['length_samples']
                clp.IO['input']['sample_rate'] = input_file_info['sample_rate']
                clp.IO['input']['channels'] = input_file_info['channels']
                clp.IO['input']['numtype'] = input_file_info['numtype']
                
                update_input_file_length_units(self.input_length.units.currentIndex())
                self.input_rate.set_value(str(EngNumber(input_file_info['sample_rate'])))
                self.num_input_channels.set_value(input_file_info['channels'])
                update_num_input_channels(input_file_info['channels'])
                self.input_channel.setEnabled(True)
                self.input_depth.set_value(input_file_info['numtype'])
                
                if clp.project['use_input_rate']:
                    if clp.project['sample_rate'] != clp.IO['input']['sample_rate']:
                        chirp_tab.update_sample_rate(new_rate=clp.IO['input']['sample_rate'])
                
                self.input_file.text_box.setStyleSheet('')
                
            except FileNotFoundError:
                clp.IO['input']['length_samples'] = 0
                clp.IO['input']['sample_rate'] = 0
                clp.IO['input']['channels'] = 0
                clp.IO['input']['numtype'] = ''
                
                self.input_length.set_value('file not found')
                self.input_rate.set_value('')
                self.num_input_channels.set_value('')
                self.input_channel.setEnabled(False)
                self.input_depth.set_value('')
                
                self.input_file.text_box.setStyleSheet('QLineEdit { background-color: orange; }')
        chirp_tab.update_input_file = update_input_file
        self.input_file.update_callback = update_input_file
        self.update_input_file = update_input_file # make inner function callable as a method
        
        # input length
        self.input_length = CLParameter('Input file length', 0, ['Sec','Samples'])
        self.input_length.text_box.setEnabled(False)
        layout.addWidget(self.input_length)
        def update_input_file_length_units(index):
            if clp.IO['input']['length_samples']:
                if index: # samples
                    self.input_length.set_value(clp.IO['input']['length_samples'])
                else: # seconds
                    self.input_length.set_value(round(clp.IO['input']['length_samples'] / clp.IO['input']['sample_rate'],2))
        self.input_length.units_update_callback = update_input_file_length_units
        
        # input sample rate
        self.input_rate = CLParameter('Sample rate', 0, 'Hz')
        self.input_rate.text_box.setEnabled(False)
        layout.addWidget(self.input_rate)
        
        # input bit depth
        self.input_depth = CLParameter('Number format', '')
        self.input_depth.text_box.setEnabled(False)
        layout.addWidget(self.input_depth)
        
        # number of input channels
        self.num_input_channels = CLParameter('Number of channels', 0)
        self.num_input_channels.text_box.setEnabled(False)
        layout.addWidget(self.num_input_channels)
        def update_num_input_channels(new_value):
            # determine input channel before rebuilding channel dropdown list
            if clp.project['input']['channel']>clp.IO['input']['channels']:
                channel_index = 0
                clp.project['input']['channel'] = 1
            else:
                channel_index = clp.project['input']['channel'] - 1
            
            # rebuild channel dropdown list (updates trigger callback, which resets output channel to 0/'all')
            self.input_channel.dropdown.clear()
            self.input_channel.dropdown.addItems([str(chan) for chan in range(1, clp.IO['input']['channels']+1)])
            
            # set correct output channel
            self.input_channel.dropdown.setCurrentIndex(channel_index)            
        self.num_input_channels.update_callback = update_num_input_channels
        
        # input channel dropdown        
        self.input_channel = CLParamDropdown('Channel', ['1'])
        layout.addWidget(self.input_channel)
        def update_input_channel(index):
            clp.project['input']['channel'] = index + 1
        self.input_channel.update_callback = update_input_channel
        
        # prepopulate input file info
        update_input_file(clp.project['input']['file'])
        
        self.analyze_button = QPushButton('Analyze')
        layout.addWidget(self.analyze_button)
        self.analyze_button.clicked.connect(chirp_tab.analyze)


class DeviceInput(QFrame):
    def __init__(self, chirp_tab):
        super().__init__()

        layout = QVBoxLayout(self)


class ResizableStackedWidget(QStackedWidget):
    def __init__(self):
        super().__init__()

        def onCurrentChanged(current_index):
            for i in range(self.count()):
                if i==current_index:
                    self.widget(i).setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                else:
                    self.widget(i).setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
                self.widget(i).adjustSize()
            self.adjustSize()
        self.currentChanged.connect(onCurrentChanged)

    def addWidget(self, widget):
        widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        super().addWidget(widget)

    