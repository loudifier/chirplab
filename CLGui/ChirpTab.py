import CLProject as clp
from CLGui import CLTab, CLParameter, CLParamNum, CLParamDropdown, CLParamFile
from CLAnalysis import generate_stimulus, read_response, generate_stimulus_file
import numpy as np
from qtpy.QtWidgets import QComboBox, QPushButton, QCheckBox, QAbstractSpinBox, QFileDialog
import pyqtgraph as pg
from engineering_notation import EngNumber
from CLGui.CLTab import toggle_section

# First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
class ChirpTab(CLTab):
    def __init__(self):
        super().__init__()
        #self.graph.axes.set_title('Stimulus Signal / Captured Response')
        self.graph.setTitle('Stimulus Signal / Captured Response') 
        self.graph.setLabel('left', 'Amplitude (FS)') # option to display units in V or Pa?
        
        
        
        # Chirp parameters section
        self.chirp_params = self.addPanelSection('Chirp Parameters')
        
        self.start_freq = CLParamNum('Start Freq', clp.project['start_freq'], 'Hz', clp.MIN_CHIRP_FREQ, clp.project['sample_rate']/2)
        self.chirp_params.addWidget(self.start_freq)
        def update_start_freq(new_value):
            if new_value == self.stop_freq.value: # catch any other invalid values (min/max are caught automatically)
                # don't catch start_freq being higher than stop_freq. Down-swept chirps technically still work with most measurements
                self.start_freq.revert() # revert and do nothing
            else:
                clp.project['start_freq'] = float(new_value) # apply the new value to the project
                self.updateStimulus() # update the stimulus (which updates the measurements)
        self.start_freq.update_callback = update_start_freq
        
        self.stop_freq = CLParamNum('Stop Freq', clp.project['stop_freq'], 'Hz', clp.MIN_CHIRP_FREQ, clp.project['sample_rate']/2)
        self.chirp_params.addWidget(self.stop_freq)
        def update_stop_freq(new_value):
            if new_value == self.start_freq.value:
                self.stop_freq.revert()
            else:
                clp.project['stop_freq'] = float(new_value)
                self.updateStimulus()
        self.stop_freq.update_callback = update_stop_freq
        
        self.chirp_length = CLParamNum('Chirp Length', clp.project['chirp_length'], ['Sec','Samples'], clp.MIN_CHIRP_LENGTH, clp.MAX_CHIRP_LENGTH, 'float')
        self.chirp_params.addWidget(self.chirp_length)
        def update_chirp_length(new_value):
            if self.chirp_length.units.currentIndex()==0: # update seconds directly
                clp.project['chirp_length'] = self.chirp_length.value
            else: # convert samples to seconds
                clp.project['chirp_length'] = self.chirp_length.value / clp.project['sample_rate']
            self.updateStimulus()
        self.chirp_length.update_callback = update_chirp_length
        def update_chirp_length_units(index):
            if index==0: # seconds
                self.chirp_length.set_numtype('float')
                self.chirp_length.min = clp.MIN_CHIRP_LENGTH
                self.chirp_length.max = clp.MAX_CHIRP_LENGTH
                self.chirp_length.set_value(clp.project['chirp_length'])
            else:
                self.chirp_length.set_numtype('int')
                self.chirp_length.min = clp.MIN_CHIRP_LENGTH*clp.project['sample_rate']
                self.chirp_length.max = clp.MAX_CHIRP_LENGTH*clp.project['sample_rate']
                self.chirp_length.set_value(clp.project['chirp_length']*clp.project['sample_rate'])
        self.chirp_length.units_update_callback = update_chirp_length_units
        
        
        
        
        # Output file or audio device section
        self.output_params = self.addPanelSection('Output')
        toggle_section(self.output_params) # start with output section collapsed
        
        #self.output_mode_dropdown = QComboBox()
        #self.output_params.addWidget(self.output_mode_dropdown)
        #self.output_mode_dropdown.addItem('File')
        
        # amplitude - dB/Fs dropdown
        self.output_amplitude = CLParamNum('Amplitude', clp.project['output']['amplitude'], ['Fs', 'dBFS'], 0, 1.0, 'float')
        self.output_amplitude.spin_box.setDecimals(5)
        self.output_params.addWidget(self.output_amplitude)
        def update_output_amplitude(new_value):
            if self.output_amplitude.units.currentIndex()==0: # FS
                clp.project['output']['amplitude'] = new_value
            else: # dBFS
                clp.project['output']['amplitude'] = 10**(new_value/20)
        self.output_amplitude.update_callback = update_output_amplitude
        def update_output_amplitude_units(index):
            if index==0: # FS
                self.output_amplitude.min = 0
                self.output_amplitude.max = 1.0
                self.output_amplitude.spin_box.setStepType(QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
                self.output_amplitude.set_value(clp.project['output']['amplitude'])
            else: # dBFS
                self.output_amplitude.min = float('-inf')
                self.output_amplitude.max = 0
                self.output_amplitude.spin_box.setStepType(QAbstractSpinBox.StepType.DefaultStepType)
                self.output_amplitude.set_value(20*np.log10(clp.project['output']['amplitude']))
        self.output_amplitude.units_update_callback = update_output_amplitude_units
            
        # pre padding - s/sample dropdown
        self.output_pre_sweep = CLParamNum('Pre Sweep', clp.project['output']['pre_sweep'], ['Sec', 'Samples'], 0, clp.MAX_ZERO_PAD, 'float')
        self.output_params.addWidget(self.output_pre_sweep)
        def update_output_pre_sweep(new_value):
            if self.output_pre_sweep.units.currentIndex()==0: # sec
                clp.project['output']['pre_sweep'] = new_value
            else: # samples
                clp.project['output']['pre_sweep'] = new_value / clp.project['output']['sample_rate']
            update_output_length()
        self.output_pre_sweep.update_callback = update_output_pre_sweep
        def update_output_pre_sweep_units(index):
            if index==0: # sec
                self.output_pre_sweep.max = clp.MAX_ZERO_PAD
                self.output_pre_sweep.set_numtype('float')
                self.output_pre_sweep.set_value(clp.project['output']['pre_sweep'])
            else: # samples
                self.output_pre_sweep.max = clp.MAX_ZERO_PAD * clp.project['output']['sample_rate']
                self.output_pre_sweep.set_value(clp.project['output']['pre_sweep'] * clp.project['output']['sample_rate'])
                self.output_pre_sweep.set_numtype('int')
        self.output_pre_sweep.units_update_callback = update_output_pre_sweep_units
        
        # post padding - s/sample dropdown
        self.output_post_sweep = CLParamNum('Post Sweep', clp.project['output']['post_sweep'], ['Sec', 'Samples'], 0, clp.MAX_ZERO_PAD, 'float')
        self.output_params.addWidget(self.output_post_sweep)
        def update_output_post_sweep(new_value):
            if self.output_post_sweep.units.currentIndex()==0: # sec
                clp.project['output']['post_sweep'] = new_value
            else: # samples
                clp.project['output']['post_sweep'] = new_value / clp.project['output']['sample_rate']
            update_output_length()
        self.output_post_sweep.update_callback = update_output_post_sweep
        def update_output_post_sweep_units(index):
            if index==0: # sec
                self.output_post_sweep.max = clp.MAX_ZERO_PAD
                self.output_post_sweep.set_numtype('float')
                self.output_post_sweep.set_value(clp.project['output']['post_sweep'])
            else: # samples
                self.output_post_sweep.max = clp.MAX_ZERO_PAD * clp.project['output']['sample_rate']
                self.output_post_sweep.set_value(clp.project['output']['post_sweep'] * clp.project['output']['sample_rate'])
                self.output_post_sweep.set_numtype('int')
        self.output_post_sweep.units_update_callback = update_output_post_sweep_units
        
        # include leading silence checkbox
        self.include_silence = QCheckBox('Include leading silence')
        self.include_silence.setChecked(clp.project['output']['include_silence'])
        self.output_params.addWidget(self.include_silence)
        
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
        self.output_length = CLParameter('Total stimulus length', calc_output_length('seconds'), ['Sec','Samples'])
        self.output_length.text_box.setEnabled(False)
        self.output_params.addWidget(self.output_length)
        def update_output_length():
            if self.output_length.units.currentIndex()==0:
                self.output_length.set_value(calc_output_length('seconds'))
            else:
                self.output_length.set_value(calc_output_length('samples'))
        def update_output_length_units(index):
            update_output_length()
        self.output_length.units_update_callback = update_output_length_units
        
        # sample rate
        self.output_sample_rate = CLParamDropdown('Sample Rate', [str(EngNumber(rate)) for rate in clp.OUTPUT_SAMPLE_RATES], 'Hz')
        output_rate_index = self.output_sample_rate.dropdown.findText(str(EngNumber(clp.project['output']['sample_rate'])))
        if output_rate_index != -1:
            self.output_sample_rate.dropdown.setCurrentIndex(output_rate_index)
        self.output_params.addWidget(self.output_sample_rate)
        def update_output_rate(index):
            clp.project['output']['sample_rate'] = clp.OUTPUT_SAMPLE_RATES[index]
            if self.output_pre_sweep.units.currentIndex()==1:
                self.output_pre_sweep.set_value(clp.project['output']['pre_sweep']*clp.project['output']['sample_rate'])
            if self.output_post_sweep.units.currentIndex()==1:
                self.output_post_sweep.set_value(clp.project['output']['post_sweep']*clp.project['output']['sample_rate'])
            update_output_length()
        self.output_sample_rate.update_callback = update_output_rate
            
        
        # bit depth (dropdown - 16 int, 24 int, 32 int, 32 float)
        self.output_bit_depth = CLParamDropdown('Bit Depth', clp.OUTPUT_BIT_DEPTHS, '')
        output_depth_index = self.output_bit_depth.dropdown.findText(clp.project['output']['bit_depth'])
        if output_depth_index != -1:
            self.output_bit_depth.dropdown.setCurrentIndex(output_depth_index)
        self.output_params.addWidget(self.output_bit_depth)
        def update_output_depth(index):
            clp.project['output']['bit_depth'] = clp.OUTPUT_BIT_DEPTHS[index]
        self.output_bit_depth.update_callback = update_output_depth
        
        # Number of output channels spinbox
        self.num_output_channels = CLParamNum('Number of channels', clp.project['output']['num_channels'],None, 1, clp.MAX_OUTPUT_CHANNELS, 'int')
        self.output_params.addWidget(self.num_output_channels)
        def update_num_output_channels(new_value):
            clp.project['output']['num_channels'] = new_value
            
            # determine output channel before rebuilding channel dropdown list
            if clp.project['output']['channel']=='all' or clp.project['output']['channel']>clp.project['output']['num_channels']:
                channel_index = 0
            else:
                channel_index = clp.project['output']['channel']
            
            # rebuild channel dropdown list (updates trigger callback, which resets output channel to 0/'all')
            self.output_channel.dropdown.clear()
            self.output_channel.dropdown.addItem('all')
            self.output_channel.dropdown.addItems([str(chan) for chan in range(1, clp.project['output']['num_channels']+1)])
            
            # set correct output channel
            self.output_channel.dropdown.setCurrentIndex(channel_index)            
        self.num_output_channels.update_callback = update_num_output_channels
        
        # output channel dropdown
        self.output_channel = CLParamDropdown('Output Channel', ['all'])
        self.output_channel.dropdown.addItems([str(chan) for chan in range(1, clp.project['output']['num_channels']+1)])
        self.output_params.addWidget(self.output_channel)
        def update_output_channel(index):
            if index==0:
                clp.project['output']['channel'] = 'all'
            else:
                clp.project['output']['channel'] = index
        self.output_channel.update_callback = update_output_channel
        
        # save file button (opens browse window)
        self.output_file_button = QPushButton('Generate Chirp Stimulus File')
        self.output_params.addWidget(self.output_file_button)
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
        
        
        
        # Input file or audio device section
        self.input_params = self.addPanelSection('Input')
        
        #self.input_mode_dropdown = QComboBox()
        #self.input_params.addWidget(self.input_mode_dropdown)
        #self.input_mode_dropdown.addItem('File')
        
        self.input_file = CLParamFile('Input File', clp.project['input']['file'])
        self.input_file.mime_types = ['audio/wav', 'application/octet-stream']
        self.input_params.addWidget(self.input_file)
        
        self.input_channel = CLParameter('Channel', clp.project['input']['channel'], '')
        self.input_params.addWidget(self.input_channel)
        
        self.analyze_button = QPushButton('Analyze')
        self.input_params.addWidget(self.analyze_button)
        self.analyze_button.clicked.connect(self.analyze)
        
        
        # Chirp analysis parameters
        self.analysis_params = self.addPanelSection('Analysis Parameters')
        
        self.sample_rate = CLParameter('Sample Rate', clp.project['sample_rate'], 'Hz')
        self.analysis_params.addWidget(self.sample_rate)
        
        self.pre_sweep = CLParameter('Pre Sweep', clp.project['pre_sweep'], 'Sec')
        self.analysis_params.addWidget(self.pre_sweep)
        
        self.post_sweep = CLParameter('Post Sweep', clp.project['post_sweep'], 'Sec')
        self.analysis_params.addWidget(self.post_sweep)
        
        # plot stimulus/response signals
        self.plot()
        

    def updateStimulus(self):
        # generate new stimulus from chirp and analysis parameters
        generate_stimulus()
        
        # update chirp tab graph and rerun measurements
        self.analyze()
        
        
    def analyze(self):
        # read in input file
        read_response() # reads in raw response, gets desired channel, and puts segment containing chirp in clp.signals['stimulus']

        # update chirp tab graph
        self.plot()

        # update measurements
        for measurement in clp.measurements:
            measurement.measure()
            measurement.plot()
            measurement.format_graph()
    
    # plot stimulus, response, and noise
    def plot(self):
        self.graph.clear()
        
        if self.chirp_length.units.currentIndex() == 0: #times in seconds
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



       