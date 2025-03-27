import CLProject as clp
from CLAnalysis import freq_points, interpolate, resample, find_offset
from CLGui import CLParamDropdown, FreqPointsParams
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal.windows import hann
import numpy as np
from CLMeasurements import CLMeasurement, PhaseResponse
from scipy.stats import linregress
from qtpy.QtWidgets import QCheckBox
from copy import deepcopy

# good resource about phase and group delay: http://cjs-labs.com/sitebuildercontent/sitebuilderfiles/GroupDelay.pdf
# UI and parameters are mostly a copy of PhaseResponse, calculation calls PhaseResponse

class GroupDelay(CLMeasurement):
    measurement_type_name = 'Group Delay'
    
    TIMING_MODES = ['absolute', 'relative']
    OUTPUT_UNITS = ['ms']
    
    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)
        self.params['type'] = 'GroupDelay'

        if len(params)<3: # populate default measurement parameters if none are provided
            # add new keys to existing dict instead of defining new one, so updates will propogate to full project dict and can be easily saved to a project file
            self.params['mode'] = 'excess' # options are 'excess' which attempts to find the effective phase assuming 0Hz phase is 0 or -180 degrees, and 'relative' which uses a loopback channel as the t=0 reference
            self.params['excess_method'] = 'linear_phase' # options are 'linear_phase' which aligns to a linear regression of the phase over the chirp, 'min_delay' which aligns phase to an estimate of the minimum group delay, and 'cross_correlation' which uses the time alignment determined by cross correlation when reading the input signal
            self.params['ref_channel'] = 2 # loopback input channel used as the phase reference in 'relative' mode. If there is no input channel ref_channel or ref_channel is the same as the project input channel the measurement will output -1 for all frequency points
            # self.params['unwrap'] = True # group delay from wrapped phase is sort of nonsensical
            # self.params['auto_invert'] = False # absolute phase does not impact group delay

            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'ms',
                'min_freq': 20,
                'min_auto': True,
                'max_freq': 20000,
                'max_auto': True,
                'spacing': 'octave',
                'num_points': 12,
                'round_points': False}
        
        # update min/max output frequencies if they are set to auto
        if self.params['output']['min_auto']:
            self.params['output']['min_freq'] = self.calc_auto_min_freq()
        if self.params['output']['max_auto']:
            self.params['output']['max_freq'] = self.calc_auto_max_freq()

        self.phase_response = PhaseResponse('phase')
        self.phase_response.params['mode'] = self.params['mode']
        self.phase_response.params['excess_method'] = self.params['excess_method']
        self.phase_response.params['ref_channel'] = self.params['ref_channel']

        self.phase_response.params['unwrap'] = True # unwrapping and absolute phase don't actually impact group delay
        self.phase_response.params['auto_invert'] = False

        # linear spacing with high frequency resolution helps keep unwrapping accurate up to higher frequencies
        # min, max, and num_points are updated before running phase response measurement
        self.phase_response.params['output'] = {'unit': 'degrees',
                                                'min_freq': 1,
                                                'min_auto': False,
                                                'max_freq': 24000,
                                                'max_auto': False,
                                                'spacing': 'linear', 
                                                'num_points': 24000,
                                                'round_points': False}
            
            
    def measure(self):
        # get phase using phase response measurement
        phase_freqs = fftfreq(len(clp.signals['stimulus']), 1/clp.project['sample_rate'])
        phase_freqs = phase_freqs[1:round(len(phase_freqs)/2)]
        self.phase_response.params['output']['min_freq'] = phase_freqs[0]
        self.phase_response.params['output']['max_freq'] = phase_freqs[-1]
        self.phase_response.params['output']['num_points'] = len(phase_freqs)
        self.phase_response.measure()
        phase = self.phase_response.out_points

        # convert phase to group delay
        delay = -(np.roll(phase,-1)-np.roll(phase,1))/(360*phase_freqs[1])
        delay *= 1000 # convert seconds to ms

        # generate array of output frequency points
        self.out_freqs = freq_points(self.params['output']['min_freq'], 
                                     self.params['output']['max_freq'],
                                     self.params['output']['num_points'],
                                     self.params['output']['spacing'],
                                     self.params['output']['round_points'])
        
        # interpolate output points
        self.out_points = interpolate(phase_freqs, delay, self.out_freqs, self.params['output']['spacing']=='linear')
        
        
        
    def init_tab(self):
        super().init_tab()

        # timing mode dropdown
        self.mode = CLParamDropdown('Timing mode', ['excess phase', 'relative phase'])
        if self.params['mode'] == 'relative':
            self.mode.dropdown.setCurrentIndex(1)
        self.param_section.addWidget(self.mode)
        def update_mode(index):
            if index:
                self.params['mode'] = 'relative'
            else:
                self.params['mode'] = 'excess'
            self.phase_response.params['mode'] = self.params['mode']
            self.excess_method.dropdown.setEnabled(not index)
            self.ref_channel.dropdown.setEnabled(bool(index))
            self.measure()
            self.plot()
        self.mode.update_callback = update_mode

        # excess phase calculation method dropdown
        self.excess_method = CLParamDropdown('Excess phase method', ['minimum group delay', 'linear phase', 'cross-correlation'])
        if self.params['excess_method'] == 'linear_phase':
            self.excess_method.dropdown.setCurrentIndex(1)
        if self.params['excess_method'] == 'cross_correlation':
            self.excess_method.dropdown.setCurrentIndex(2)
        self.excess_method.dropdown.setEnabled(self.params['mode'] != 'relative')
        self.param_section.addWidget(self.excess_method)
        def update_excess_method(index):
            if index==0:
                self.params['excess_method'] = 'min_delay'
            if index==1:
                self.params['excess_method'] = 'linear_phase'
            if index==2:
                self.params['excess_method'] = 'cross_correlation'
            self.phase_response.params['excess_method'] = self.params['excess_method']
            self.measure()
            self.plot()
        self.excess_method.update_callback = update_excess_method

        # relative phase reference channel dropdown
        self.ref_channel = CLParamDropdown('Loopback reference channel', [''])
        self.ref_channel.dropdown.setEnabled(self.params['mode'] == 'relative')
        self.param_section.addWidget(self.ref_channel)
        def update_ref_channel(index): # todo: still some corner cases that need to be worked out
            self.params['ref_channel'] = int(self.ref_channel.dropdown.currentText())
            self.phase_response.params['ref_channel'] = self.params['ref_channel']
            
            if self.params['ref_channel'] == clp.project['input']['channel']:
                self.ref_channel.dropdown.setStyleSheet('QComboBox { background-color: orange; }')
            else:
                self.ref_channel.dropdown.setStyleSheet('')

            if self.params['mode'] == 'relative':
                self.measure()
                self.plot()
        self.ref_channel.update_callback = update_ref_channel
        def update_num_channels(num_channels):
            channel_list = [str(chan) for chan in range(1, num_channels+1)]
            # todo: figure out how to build list without reference channel. Introduces a lot of weird state management issues

            self.ref_channel.dropdown.blockSignals(True)
            self.ref_channel.dropdown.clear()
            self.ref_channel.dropdown.addItems(channel_list)
            if self.params['ref_channel'] <= num_channels:
                self.ref_channel.dropdown.setCurrentIndex(channel_list.index(str(self.params['ref_channel'])))
            self.ref_channel.dropdown.blockSignals(False)
            
            if self.params['ref_channel'] <= num_channels:
                update_ref_channel(channel_list.index(str(self.params['ref_channel'])))
            else:
                self.ref_channel.dropdown.setStyleSheet('QComboBox { background-color: orange; }')
        self.update_num_channels = update_num_channels
        self.update_num_channels(clp.IO['input']['channels'])


        # output section
        self.output_unit = CLParamDropdown('Units', self.OUTPUT_UNITS, '')
        output_unit_index = self.output_unit.dropdown.findText(self.params['output']['unit'])
        if output_unit_index != -1:
            self.output_unit.dropdown.setCurrentIndex(output_unit_index)
        self.output_section.addWidget(self.output_unit)
        def update_output_unit(index):
            self.params['output']['unit'] = self.OUTPUT_UNITS[index]
            self.measure()
            self.plot()
            self.format_graph()
        self.output_unit.update_callback = update_output_unit
        
        self.output_points = FreqPointsParams(self.params['output'])
        self.output_section.addWidget(self.output_points)
        def update_output_points():
            self.measure()
            self.plot()
            self.format_graph()
        self.output_points.update_callback = update_output_points
        self.output_points.calc_min_auto = self.calc_auto_min_freq
        self.output_points.calc_max_auto = self.calc_auto_max_freq
    

    def update_tab(self):
        self.update_num_channels(clp.IO['input']['channels'])
        self.output_points.update_min_max()
        
    def calc_auto_min_freq(self):
        return clp.project['start_freq']
    
    def calc_auto_max_freq(self):
        return min(clp.project['stop_freq'], (clp.project['sample_rate']/2) * 0.9)
