import CLProject as clp
from CLGui import CLTab, CLParameter, CLParamNum, clear_plot
from CLAnalysis import generate_stimulus, read_response
import numpy as np
from qtpy.QtWidgets import QComboBox, QPushButton

# First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
class ChirpTab(CLTab):
    def __init__(self):
        super().__init__()
        self.graph.axes.set_title('Stimulus Signal / Captured Response')
        self.graph.axes.set_ylabel('Amplitude (FS)') # option to display units in V or Pa?
        
        # Chirp parameters section
        self.chirp_params = self.addPanelSection('Chirp Parameters')
        
        self.start_freq = CLParamNum('Start Freq', clp.project['start_freq'], 'Hz', clp.MIN_CHIRP_FREQ, clp.project['sample_rate']/2)
        self.chirp_params.addWidget(self.start_freq)
        def updateStartFreq(new_value):
            if new_value == self.stop_freq.value: # catch any other invalid values (min/max are caught automatically)
                # don't catch start_freq being higher than stop_freq. Down-swept chirps technically still work with most measurements
                self.start_freq.revert() # revert and do nothing
            else:
                clp.project['start_freq'] = float(new_value) # apply the new value to the project
                self.updateStimulus() # update the stimulus (which updates the measurements)
        self.start_freq.update_callback = updateStartFreq
        
        self.stop_freq = CLParamNum('Stop Freq', clp.project['stop_freq'], 'Hz', clp.MIN_CHIRP_FREQ, clp.project['sample_rate']/2)
        self.chirp_params.addWidget(self.stop_freq)
        def updateStopFreq(new_value):
            if new_value == self.start_freq.value:
                self.stop_freq.revert()
            else:
                clp.project['stop_freq'] = float(new_value)
                self.updateStimulus()
        self.stop_freq.update_callback = updateStopFreq
        
        self.chirp_length = CLParamNum('Chirp Length', clp.project['chirp_length'], ['Sec','Samples'], clp.MIN_CHIRP_LENGTH, clp.MAX_CHIRP_LENGTH, 'float')
        self.chirp_params.addWidget(self.chirp_length)
        def updateChirpLength(new_value):
            if self.chirp_length.units.currentIndex() == 0: # update seconds directly
                clp.project['chirp_length'] = self.chirp_length.value
            else: # convert samples to seconds
                clp.project['chirp_length'] = self.chirp_length.value / clp.project['sample_rate']
            self.updateStimulus()
        self.chirp_length.update_callback = updateChirpLength
        def updateChirpLengthUnits(index):
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
        self.chirp_length.units_update_callback = updateChirpLengthUnits
        
        self.output_params = self.addPanelSection('Output')
        
        
        # Input file or audio device section
        self.input_params = self.addPanelSection('Input')
        
        self.input_mode_dropdown = QComboBox()
        self.input_params.addWidget(self.input_mode_dropdown)
        self.input_mode_dropdown.addItem('File')
        
        self.input_file_box = CLParameter('Input File', clp.project['input']['file'], '')
        self.input_params.addWidget(self.input_file_box)
        
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
        # self.graph.axes.cla() # much faster to update plots in place and requires setting title/label/etc every time, but updating in place only works for same size data and does not automatically update ranges
        clear_plot(self.graph.axes)
        
        if self.chirp_length.units.currentIndex() == 0: #times in seconds
            times = np.arange(len(clp.signals['stimulus']))/clp.project['sample_rate'] - clp.project['pre_sweep']
            self.graph.axes.set_xlabel('Time (seconds)')
        else: #times in samples
            times = np.arange(len(clp.signals['stimulus'])) - round(clp.project['pre_sweep']*clp.project['sample_rate'])
            self.graph.axes.set_xlabel(' Time (samples)')
        self.graph.axes.plot(times, clp.signals['stimulus'], label='stimulus')
        self.graph.axes.plot(times, clp.signals['response'], label='response')
        if any(clp.signals['noise']):
            self.graph.axes.plot(times, clp.signals['noise'], label='noise sample', color='gray')
        self.graph.axes.legend()
        self.graph.draw()


       