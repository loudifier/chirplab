import CLProject as clp
from CLAnalysis import chirp_freq_to_time, freq_points, interpolate, FS_to_unit
from CLGui import CLParamNum, CLParamDropdown, FreqPointsParams
import numpy as np
from CLMeasurements import CLMeasurement

# tracking filter implementation to perform measurements roughly equivalent to Audio Precision's Rub and Buzz Peak Ratio and Crest Factor. https://www.ap.com/fileadmin-ap/technical-library/appnote-rub-buzz.pdf
# for a Peak Ratio-style measurement, apply a highpass filter at 5-30x the fundamental and output the 'filtered peak' signal relative to the 'fundamental' or 'raw' signal
# for a Crest Factor-style measurement, apply a highpass filter at 5-30x the fundamental and output the 'filtered peak' signal relative to the 'filtered RMS' signal
# additional filters available as an alternative to impulse response-based frequency response or harmonic distortion measurements. e.g. bandpass filter at 1x fundamental frequency for frequency response or 2x for second harmonic, notch at 1x fundamental for a rough THD+N approximation, etc.

class TrackingFilter(CLMeasurement):
    measurement_type_name = 'Tracking Filter'
    
    ABSOLUTE_OUTPUT_UNITS = ['dBFS', 'dBSPL', 'dBV', 'FS', 'Pa', 'V']
    RELATIVE_OUTPUT_UNITS = ['dB', '%', '% (IEC method)']
    
    # set of response signals that can be selected for measurement output or as a reference for relative measurements
    SIGNALS = ['raw',           # unfiltered response
               'fundamental',   # bandpass filtered response, 1x fundamental frequency, Q=10
               'filtered peak', # peak level of the response signal filtered using the set of filters given in params['filters']. Peak is the max level in the interval of samples around each output frequency point
               'filtered RMS']  # RMS level of the filtered response signal
    
    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)
        self.params['type'] = 'TrackingFilter'

        if len(params)<3: # default measurement parameters
            self.params['filters'] = [ # bank of 2nd order filters to apply to the response signal
                {'multiplier': 10,     # the corner or center frequency of the filter ("wherever it's happenin', man") as a ratio of the instantaneous chirp frequency. e.g. for a multiplier of 10, when the chirp frequency is 1kHz the filter frequency will be 10kHz. Very high filter frequencies will be limited to 0.95*Nyquist
                 'type': 'highpass',   # options are 'lowpass', 'highpass', 'bandpass' (constant peak=0dB at center frequency), and 'notch'
                 'Q': 0.5},            # Q of the filter
                {'multiplier': 10,
                 'type': 'highpass',   # default filters results in a 4th order Butterworth highpass at 10x chirp frequency
                 'Q': 0.5}]
                # todo: add an option to define elliptical or higher order filters usng scipy.signal.iirdesign() or similar? Would make it easier for poeple to specify very sharp cutoffs, 8+ order Butterworth, etc. Actual filter processing would be pretty similar to biquad calculations by using 'sos' conversion
            self.params['mode'] = 'relative' # output the filtered response amplitude 'relative' to a reference signal or 'absolute'
            self.params['measured_signal'] = 'filtered peak' # 'filtered peak' relative to 'filtered RMS' is roughly equivalent to AP's Rub and Buzz Crest Factor measurement
            self.params['reference_signal'] = 'filtered RMS'
            self.params['rms_unit'] = 'octaves' # method of specifying the amount of time to apply a moving RMS calculation over the measured and/or filtered response signals. Either 'octaves' to specify a frequency range determined by the chirp sweep rate, or 'seconds' for a fixed amount of time independent of the sweep rate
            self.params['rms_time'] = 1/3 # rms_unit='octave's and rms_time=1/3 for a 1s chirp from 20-20kHz (9.97 octaves) results in a sliding RMS calculation window of 33.4ms

            
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dB', # options are 'dB' or '%' relative to fundamental
                'min_freq': 20,
                'min_auto': True, # min_freq ignored and updated if True
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

            
    def measure(self):
        self.out_freqs = [clp.project['start_freq'], clp.project['stop_freq']]
        self.out_points = [0,0]
    
    
        
    def init_tab(self):
        super().init_tab()

        # measurement parameters

        
        self.output_unit = CLParamDropdown('Units', [unit for unit in self.RELATIVE_OUTPUT_UNITS], '')
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
        self.output_points.update_min_max()
    
    def calc_auto_min_freq(self):
        return clp.project['start_freq']
    
    def calc_auto_max_freq(self):
        # todo: make this function smarter. Does it make sense to just divide stop_freq by max filter frequency multiplier
        return clp.project['stop_freq']
