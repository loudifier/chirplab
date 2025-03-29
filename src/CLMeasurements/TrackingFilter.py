import CLProject as clp
from CLAnalysis import chirp_time_to_freq, chirp_freq_to_time, freq_points, interpolate, FS_to_unit
from CLGui import CLParamNum, CLParamDropdown, FreqPointsParams, QCollapsible, QHSeparator
import numpy as np
from CLMeasurements import CLMeasurement
from Biquad import Biquad, lowpass_coeff, highpass_coeff, bandpass_coeff, notch_coeff
import pandas as pd
from qtpy.QtWidgets import QFrame, QVBoxLayout, QAbstractSpinBox, QPushButton

# tracking filter implementation to perform measurements roughly equivalent to Audio Precision's Rub and Buzz Peak Ratio and Crest Factor. https://www.ap.com/fileadmin-ap/technical-library/appnote-rub-buzz.pdf
# for a Peak Ratio-style measurement, apply a highpass filter at 5-30x the fundamental and measure the 'filtered peak' signal relative to the 'fundamental RS' or 'unfiltered RMS' signal
# for a Crest Factor-style measurement, apply a highpass filter at 5-30x the fundamental and measure the 'filtered peak' signal relative to the 'filtered RMS' signal
# additional filters available as an alternative to impulse response-based frequency response or harmonic distortion measurements. e.g. bandpass filter at 1x fundamental frequency for frequency response or 2x for second harmonic, notch at 1x fundamental for a rough THD+N approximation, etc.

class TrackingFilter(CLMeasurement):
    measurement_type_name = 'Tracking Filter'
    
    ABSOLUTE_OUTPUT_UNITS = ['dBFS', 'dBSPL', 'dBV', 'FS', 'Pa', 'V']
    RELATIVE_OUTPUT_UNITS = ['dB', '%', '% (IEC method)']
    
    # set of response signals that can be selected for measurement output or as a reference for relative measurements
    SIGNALS = ['unfiltered RMS',  # RMS of unfiltered response
               'fundamental RMS', # RMS of bandpass filtered response, 1x fundamental frequency, Q=10
               'filtered peak',   # peak level of the response signal filtered using the set of filters given in params['filters']. Peak is the max level in the interval of samples around each output frequency point
               'filtered RMS']    # RMS level of the filtered response signal
    
    # set of filter types that can be selected
    FILTER_TYPES = ['lowpass',  # 2nd order lowpass
                    'highpass', # 2nd order highpass
                    'bandpass', # constant peak (0dB at center frequency)
                    'notch']    # notch with infinite depth (within limits of numerical precision and time/phase alignment)

    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)
        self.params['type'] = 'TrackingFilter'

        if len(params)<3: # default measurement parameters
            self.params['filters'] = [ # bank of 2nd order filters to apply to the response signal
                {'multiplier': 10,     # the corner or center frequency of the filter ("wherever it's happenin', man") as a ratio of the instantaneous chirp frequency. e.g. for a multiplier of 10, when the chirp frequency is 1kHz the filter frequency will be 10kHz. Very high filter frequencies will be limited to 0.95*Nyquist
                 'type': 'highpass',   # options are 'lowpass', 'highpass', 'bandpass', and 'notch'
                 'Q': 0.707},            # Q of the filter
                {'multiplier': 10,
                 'type': 'highpass',   # default filters results in a 4th order highpass with Q=0.5 at 10x chirp frequency
                 'Q': 0.707}]
                # todo: add an option to define elliptical or higher order filters usng scipy.signal.iirdesign() or similar? Would make it easier for poeple to specify very sharp cutoffs, 8+ order Butterworth, etc. Actual filter processing would be pretty similar to biquad calculations by using 'sos' conversion
            self.params['mode'] = 'relative' # output the filtered response amplitude 'relative' to a reference signal or 'absolute'
            self.params['measured_signal'] = 'filtered peak' # 'filtered peak' relative to 'fundamental' is roughly equivalent to AP's Rub and Buzz Peak Ratio measurement
            self.params['reference_signal'] = 'fundamental RMS'
            self.params['rms_unit'] = 'octaves' # method of specifying the amount of time to apply a moving RMS calculation over the measured and/or filtered response signals. Either 'octaves' to specify a frequency range determined by the chirp sweep rate, or 'seconds' for a fixed amount of time independent of the sweep rate
            self.params['rms_time'] = 1/3 # rms_unit='octaves' and rms_time=1/3 for a 1s chirp from 20-20kHz (9.97 octaves) results in a sliding RMS calculation window of 33.4ms

            
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dB',
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
        # calculate the instantaneous chirp frequency at each sample of the response
        chirp_start_sample = round(clp.project['pre_sweep']*clp.project['sample_rate']) # calculate the exact time of the first chirp sample. todo: check if this is off by 1 sample
        response_times = (np.arange(len(clp.signals['response'])) - chirp_start_sample) / clp.project['sample_rate']
        response_freqs = chirp_time_to_freq(clp.project['start_freq'], clp.project['stop_freq'], clp.project['chirp_length'], response_times)

        # generate array of output frequency points
        self.out_freqs = freq_points(self.params['output']['min_freq'], 
                                     self.params['output']['max_freq'],
                                     self.params['output']['num_points'],
                                     self.params['output']['spacing'],
                                     self.params['output']['round_points'])

        def calc_tracking_filter(response, selected_signal):

            def multi_filter(x, b, a):
                # apply multiple biquad filter stages, each with coefficients that are updated for each sample of the input signal, x
                num_filters = len(b)
                num_samples = len(x)
                y = x.copy()

                # loop through each filter
                for f in range(num_filters):
                    biquad = Biquad()

                    # loop through samples
                    for n in range(num_samples):
                        # set filter coefficients for this sample and apply filter
                        biquad.b[0] = b[f][0][n] # there is a probably a clever slice that does this in one step, but the array outputs from Biquad.<filter>_coeff() are not in a slice-friendly shape
                        biquad.b[1] = b[f][1][n]
                        biquad.b[2] = b[f][2][n]
                        biquad.a[1] = a[f][1][n]
                        biquad.a[2] = a[f][2][n]
                        y[n] = biquad.process(y[n])

                return y

            # calculate filter coefficients for each filter and sample, and filter response signals
            if selected_signal == 'fundamental RMS':
                fund_b = [[]]
                fund_a = [[]]
                fund_b[0], fund_a[0] = bandpass_coeff(response_freqs, 10, clp.project['sample_rate'])
                response = multi_filter(response, fund_b, fund_a)
            
            if selected_signal=='filtered peak' or selected_signal=='filtered RMS':
                num_filters = len(self.params['filters'])
                filt_b = [[]] * num_filters
                filt_a = [[]] * num_filters
                for i in range(num_filters):
                    filt_freqs = np.minimum(0.95 * clp.project['sample_rate'] / 2, response_freqs * self.params['filters'][i]['multiplier'])
                    match self.params['filters'][i]['type']:
                        case 'lowpass':
                            filt_b[i], filt_a[i] = lowpass_coeff(filt_freqs, self.params['filters'][i]['Q'], clp.project['sample_rate'])
                        case 'highpass':
                            filt_b[i], filt_a[i] = highpass_coeff(filt_freqs, self.params['filters'][i]['Q'], clp.project['sample_rate'])
                        case 'bandpass':
                            filt_b[i], filt_a[i] = bandpass_coeff(filt_freqs, self.params['filters'][i]['Q'], clp.project['sample_rate'])
                        case 'notch':
                            filt_b[i], filt_a[i] = notch_coeff(filt_freqs, self.params['filters'][i]['Q'], clp.project['sample_rate'])
                
                response = multi_filter(response, filt_b, filt_a)

            # else 'unfiltered RMS': don't apply a filter

            if selected_signal == 'filtered peak':
                # instantaneous peak level of filtered response
                signal_level = np.zeros(len(self.out_freqs))
                
                # loop through response_freqs to find the maximum in the intervals around each self.out_freqs. Ugly and brute force approach, but handles a lot of corner cases that would be difficult to get right with a .rolling() solution
                j = 0 # keep track of which out_freq is being calculated
                for i in range(len(response_freqs)):

                    # skip everything below the lowest out_freq (but still initialize min_sample)
                    if response_freqs[i] < self.out_freqs[0]:
                        min_sample = i
                        continue
                    
                    # find the dividing line between the current frequency and the next frequency (this block could/probably should be moved outside of the loop)
                    if j == len(self.out_freqs) - 1: # skip everything above the highest out_freq
                        freq_boundary = self.out_freqs[-1]
                    else:
                        if self.params['output']['spacing'] == 'linear':
                            freq_boundary = (self.out_freqs[j] + self.out_freqs[j+1]) / 2
                        else:
                            freq_boundary = np.exp((np.log(self.out_freqs[j]) + np.log(self.out_freqs[j+1])) / 2)
                    
                    # find the last sample for the current out_freq
                    if response_freqs[i] < freq_boundary:
                        continue
                    signal_level[j] = max(abs(response[min_sample:i]))
                    min_sample = i
                    j += 1
                    if j == len(self.out_freqs):
                        break

            else:
                # calculate moving RMS length
                if self.params['rms_unit'] == 'octaves':
                    rms_time = (clp.project['chirp_length'] / np.log2(clp.project['stop_freq']/clp.project['start_freq'])) * self.params['rms_time']
                else:
                    rms_time = self.params['rms_time']
                rms_samples = round(rms_time * clp.project['sample_rate'])

                # calculate moving RMS
                signal_level = np.sqrt(pd.DataFrame(response*response).rolling(rms_samples, center=True, min_periods=1).mean())

                # interpolate signal_level at self.out_freqs
                signal_level = interpolate(response_freqs, np.array(signal_level)[:,0], self.out_freqs)

            return signal_level


        # convert output to desired units
        def convert_output_units(fs_points, ref_points=None):
            match self.params['output']['unit']:
                case 'dB':
                    return 20*np.log10(fs_points / ref_points)
                case '%':
                    return 100 * fs_points / ref_points
                case '% (IEC method)':
                    return 100 * fs_points / (ref_points + fs_points)
                case _:
                    return FS_to_unit(fs_points, self.params['output']['unit'])

        # todo: a lot of opportunity to optimize, avoid applying the same filters multiple times
        measured_level = calc_tracking_filter(clp.signals['response'], self.params['measured_signal'])
        if any(clp.signals['noise']):
            measured_noise = calc_tracking_filter(clp.signals['noise'], self.params['measured_signal'])
        
        if self.params['mode'] == 'absolute':
            self.out_points = convert_output_units(measured_level)
            if any(clp.signals['noise']):
                self.out_noise = convert_output_units(measured_noise)
            return

        ref_level = calc_tracking_filter(clp.signals['response'], self.params['reference_signal'])
        self.out_points = convert_output_units(measured_level, ref_level)
        if any(clp.signals['noise']):
            self.out_noise = convert_output_units(measured_noise, ref_level)
    
        
    def init_tab(self):
        super().init_tab()

        # dropdown to select measured signal
        self.measured_signal = CLParamDropdown('Measured signal', self.SIGNALS)
        signal_index = self.measured_signal.dropdown.findText(self.params['measured_signal'])
        self.measured_signal.dropdown.setCurrentIndex(signal_index)
        self.param_section.addWidget(self.measured_signal)
        def update_measured_signal(index):
            self.params['measured_signal'] = self.SIGNALS[index]
            self.measure()
            self.plot()
        self.measured_signal.update_callback = update_measured_signal

        # dropdown to select relative or absolute mode
        self.mode = CLParamDropdown('Measurement mode', ['relative', 'absolute'])
        if self.params['mode'] == 'absolute':
            self.mode.dropdown.setCurrentIndex(1)
        self.param_section.addWidget(self.mode)
        def update_mode(index):
            self.output_unit.dropdown.blockSignals(True)
            self.output_unit.dropdown.clear()
            if index:
                self.params['mode'] = 'absolute'
                self.reference_signal.dropdown.setEnabled(False)
                self.output_unit.dropdown.addItems(self.ABSOLUTE_OUTPUT_UNITS)
            else:
                self.params['mode'] = 'relative'
                self.reference_signal.dropdown.setEnabled(True)
                self.output_unit.dropdown.addItems(self.RELATIVE_OUTPUT_UNITS)
            self.output_unit.dropdown.blockSignals(False)
            update_output_unit(0) # sets relative to 'dB', sets absolute to 'dBFS'
        self.mode.update_callback = update_mode

        # dropdown to set reference signal for relative mode
        self.reference_signal = CLParamDropdown('Reference signal', self.SIGNALS)
        signal_index = self.reference_signal.dropdown.findText(self.params['reference_signal'])
        self.reference_signal.dropdown.setCurrentIndex(signal_index)
        self.param_section.addWidget(self.reference_signal)
        def update_reference_signal(index):
            self.params['reference_signal'] = self.SIGNALS[index]
            self.measure()
            self.plot()
        self.reference_signal.update_callback = update_reference_signal

        # RMS averaging time
        self.rms_time = CLParamNum('RMS time', self.params['rms_time'], ['seconds', 'octaves'])
        self.rms_time.spin_box.setDecimals(3)
        if self.params['rms_unit'] == 'octaves':
            self.rms_time.min = 1/48
            self.rms_time.units.setCurrentIndex(1)
        else:
            self.rms_time.min = 0.001
        self.param_section.addWidget(self.rms_time)
        def update_rms_time(new_val):
            self.params['rms_time'] = new_val
            self.measure()
            self.plot()
        self.rms_time.update_callback = update_rms_time
        def update_rms_time_unit(index):
            sweep_rate = clp.project['chirp_length'] / np.log2(clp.project['stop_freq'] / clp.project['start_freq'])
            if index:
                self.params['rms_unit'] = 'octaves'
                self.rms_time.min = 1/48
                self.params['rms_time'] /= sweep_rate
            else:
                self.params['rms_unit'] = 'seconds'
                self.rms_time.min = 0.001
                self.params['rms_time'] *= sweep_rate
            self.rms_time.set_value(self.params['rms_time'])
        self.rms_time.units_update_callback = update_rms_time_unit

        # collapsible section with controls for filter bank
        self.filters_section = QCollapsible('Filters')
        self.param_section.addWidget(self.filters_section)

        # list of clump of controls to configure each filter
        self.filters_params = [None]*len(self.params['filters'])
        for f in range(len(self.params['filters'])):
            self.filters_params[f] = FilterParams(self.params['filters'][f], self)
            self.filters_section.addWidget(self.filters_params[f])

        # button to remove the last filter from the list
        self.remove_filter_button = QPushButton('Remove filter')
        def remove_filter():
                self.filters_section.removeWidget(self.filters_params[-1])
                self.filters_params.pop()
                self.params['filters'].pop()
                if len(self.params['filters']) == 1: # always leave at least one filter
                    self.filters_section.removeWidget(self.remove_filter_button)
                self.measure()
                self.plot()
        self.remove_filter_button.clicked.connect(remove_filter)
        if len(self.params['filters']) > 1:
            self.filters_section.addWidget(self.remove_filter_button)
            
        # button (and horizontal separator) to add another filter to the filter bank
        self.add_button_separator = QHSeparator()
        self.filters_section.addWidget(self.add_button_separator)

        self.add_filter_button = QPushButton('Add filter')
        self.filters_section.addWidget(self.add_filter_button)
        def add_filter():
            self.params['filters'].append({'type': 'highpass',
                                          'multiplier': 10,
                                          'Q': 0.707})
            self.filters_params.append(FilterParams(self.params['filters'][-1], self))
            self.filters_section.removeWidget(self.add_filter_button)
            self.filters_section.removeWidget(self.add_button_separator)
            self.filters_section.removeWidget(self.remove_filter_button)
            self.filters_section.addWidget(self.filters_params[-1])
            self.filters_section.addWidget(self.remove_filter_button)
            self.filters_section.addWidget(self.add_button_separator)
            self.filters_section.addWidget(self.add_filter_button)
            self.measure()
            self.plot()
        self.add_filter_button.clicked.connect(add_filter)


        # output parameters
        if self.params['mode'] == 'absolute':
            self.output_unit = CLParamDropdown('Units', self.ABSOLUTE_OUTPUT_UNITS, '')
        else:
            self.output_unit = CLParamDropdown('Units', self.RELATIVE_OUTPUT_UNITS, '')
        output_unit_index = self.output_unit.dropdown.findText(self.params['output']['unit'])
        if output_unit_index != -1:
            self.output_unit.dropdown.setCurrentIndex(output_unit_index)
        self.output_section.addWidget(self.output_unit)
        def update_output_unit(index):
            self.params['output']['unit'] = self.output_unit.dropdown.currentText()
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
        # todo: make this function smarter. Does it make sense to just divide stop_freq by max filter frequency multiplier?
        return clp.project['stop_freq']

class FilterParams(QFrame):
    # pass in the parameters dict for the filter so they can be updated, and the parent TrackingFilter to make it easy to call measure() and plot()
    def __init__(self, params, measurement):
        super().__init__()

        layout = QVBoxLayout(self)

        layout.addWidget(QHSeparator())

        self.type = CLParamDropdown('Filter type', measurement.FILTER_TYPES)
        type_index = self.type.dropdown.findText(params['type'])
        self.type.dropdown.setCurrentIndex(type_index)
        layout.addWidget(self.type)
        def update_type(index):
            params['type'] = measurement.FILTER_TYPES[index]
            measurement.measure()
            measurement.plot()
        self.type.update_callback = update_type
        
        self.multiplier = CLParamNum('Frequency', params['multiplier'], 'x chirp fundamental', 0.01)
        self.multiplier.spin_box.setStepType(QAbstractSpinBox.StepType.DefaultStepType)
        layout.addWidget(self.multiplier)
        def update_multiplier(new_val):
            params['multiplier'] = new_val
            measurement.measure()
            measurement.plot()
        self.multiplier.update_callback = update_multiplier

        self.Q = CLParamNum('Q', params['Q'], '', 0.1)
        self.Q.spin_box.setDecimals(3)
        layout.addWidget(self.Q)
        def update_Q(new_val):
            params['Q'] = new_val
            measurement.measure()
            measurement.plot()
        self.Q.update_callback = update_Q
