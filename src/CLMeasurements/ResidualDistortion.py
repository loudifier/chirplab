import CLProject as clp
from CLAnalysis import chirp_time_to_freq, freq_points, interpolate, FS_to_unit, fftconv, max_in_intervals
from CLGui import CLParamNum, CLParamDropdown, FreqPointsParams
import numpy as np
from CLMeasurements import CLMeasurement, FrequencyResponse
import pandas as pd
from scipy.fftpack import fft, ifft
from scipy.signal.windows import hann
from CLMeasurements.HarmonicDistortion import harmonic_impulse_time

# method for measuring distortion in the time domain, roughly equivalent to Klippel methods https://www.klippel.de/fileadmin/klippel/Files/Know_How/Literature/Papers/Measurement_of_Rub_and_Buzz_03.pdf
# idealized response is modeled by windowing the fundamental and n harmonic impulses from the impulse response, and instantaneous distortion is the residual after subtracting the modeled response from the raw response
# Klippel likely models speaker directly from LPM/LSI measurements, impulse response method may not be as accurate.

class ResidualDistortion(CLMeasurement):
    measurement_type_name = 'Residual Distortion'
    
    OUTPUT_UNITS = ['dB', '%', '% (IEC method)', 'dBFS', 'dBSPL', 'dBV', 'FS', 'Pa', 'V'] # relative units are the selected distortion measure relative to the RMS of the raw response signal
    CREST_FACTOR_UNITS = ['dB', '%'] # for the special case of the crest factor analysis, the output is the peak residual value in each interval relative to the RMS of the residual
    
    # set of analysis modes that can be selected for how residual distortion is measured
    MODES = ['residual RMS',  # RMS of the residual signal after subtracting the modeled response from the raw response
             'residual peak', # max value of the residual distortion in each output frequency interval
             'crest factor']  # residual peak relative to residual RMS

    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)

        if len(params)<3: # default measurement parameters
            self.params['mode'] = 'peak' # which analysis mode is used. Either 'rms', 'peak', or 'crestfactor'
            self.params['rms_unit'] = 'octaves' # method of specifying the amount of time to apply a moving RMS calculation over the residual and/or raw response signals. Either 'octaves' to specify a frequency range determined by the chirp sweep rate, or 'seconds' for a fixed amount of time independent of the sweep rate
            self.params['rms_time'] = 1/3 # rms_unit='octaves' and rms_time=1/3 for a 1s chirp from 20-20kHz (9.97 octaves) results in a sliding RMS calculation window of 33.4ms
            self.params['max_harmonic'] = 7 # the transfer function model will include the fundamental response up to max_harmonic to model the linear and major nonlinearities of the transfer function. Set to 1 to only model the fundamental response, resulting in a rough THD+N measurement
            
            # harmonic window parameters copied from HarmonicDistortion. Maybe expose these in GUI or refine this process in the future if HarmonicDistortion is updated
            self.params['harmonic_window_start'] = 0.1 # windowing parameters similar to frequency response windowing, but windows are centered on harmonic impulses, numbers are expressed in proportion of time to previous/next harmonic impulse
            self.params['harmonic_fade_in'] = 0.1      # e.g. for H2 impulse arriving 10ms after H3 impulse, fade_in=0.1 results in harmonic window starting 1ms before H2 harmonic impulse
            self.params['harmonic_window_end'] = 0.9   # fade_in/out must be <= window_start/end, respectively
            self.params['harmonic_fade_out'] = 0.5     # window_start + window_end should be <1 to avoid overlap between harmonic impulse windows

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

        # generate an idealized version of the response that includes fundamental and low-order harmonics, and subtract it from the actual response
        def calc_residual(response):
            # calculate raw impulse response
            impulse_response = ifft(fft(response) / fft(clp.signals['stimulus']))

            # generate window for fundamental and harmonic range, drawing from FrequencyResponse and HarmonicDistortion methods
            # generate window using adaptive FrequencyResponse method for lowest frequency
            max_wavelength_samples = round(clp.project['sample_rate'] / self.out_freqs[0])
            window_start = max_wavelength_samples
            fade_in = max_wavelength_samples
            window_end = 2*max_wavelength_samples
            fade_out = max_wavelength_samples

            window = np.zeros(len(impulse_response))
            window[:fade_in] = hann(fade_in*2)[:fade_in]
            window[fade_in:window_start+window_end-fade_out] = np.ones(window_start-fade_in+window_end-fade_out)
            window[window_start+window_end-fade_out:window_start+window_end] = hann(fade_out*2)[fade_out:]
            window = np.roll(window, -window_start)

            # generate series of harmonic impulse windows using HarmonicDistortion method
            if self.params['max_harmonic'] > 1:
                for harmonic in range(2, self.params['max_harmonic']+1):
                    # generate harmonic window
                    harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic)
                    prev_harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic+1) # next harmonic *number*, previous in terms of *arrival time*. Used to calculate window_start
                    next_harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic-1)

                    fade_in = round(self.params['harmonic_fade_in']*(harmonic_time-prev_harmonic_time)*clp.project['sample_rate'])
                    window_start = round(self.params['harmonic_window_start']*(harmonic_time-prev_harmonic_time)*clp.project['sample_rate'])
                    fade_out = round(self.params['harmonic_fade_out']*(next_harmonic_time-harmonic_time)*clp.project['sample_rate'])
                    window_end = round(self.params['harmonic_window_end']*(next_harmonic_time-harmonic_time)*clp.project['sample_rate'])
                    
                    harmonic_window = np.zeros(len(impulse_response))
                    harmonic_window[:fade_in] = hann(fade_in*2)[:fade_in]
                    harmonic_window[fade_in:window_start+window_end-fade_out] = np.ones(window_start-fade_in+window_end-fade_out)
                    harmonic_window[window_start+window_end-fade_out:window_start+window_end] = hann(fade_out*2)[fade_out:]
                    harmonic_window = np.roll(harmonic_window, round(harmonic_time*clp.project['sample_rate']) - window_start)

                    # add harmonic window to total window
                    window += harmonic_window

            # apply impulse response with fundamental and harmonic windows to stimulus to model the transfer function without high order harmonics and reduced system noise
            modeled_response = fftconv(clp.signals['stimulus'], impulse_response*window).real

            # get the difference between the actual response and modeled response
            residual = response - modeled_response

            return residual

        residual = calc_residual(clp.signals['response'])
        if any(clp.signals['noise']):
            noise_residual = calc_residual(clp.signals['noise'])

        if self.params['mode'] != 'rms': # peak levels used for 'peak' and 'crestfactor' modes
            # instantaneous peak level of the residual distortion
            residual_peak = max_in_intervals(response_freqs, abs(residual), self.out_freqs, linear=self.params['output']['spacing']=='linear')
            if any(clp.signals['noise']):
                noise_peak = max_in_intervals(response_freqs, abs(noise_residual), self.out_freqs, linear=self.params['output']['spacing']=='linear')

         # calculate moving RMS length (not used in every case, but in most situations)
        if self.params['rms_unit'] == 'octaves':
            rms_time = (clp.project['chirp_length'] / np.log2(clp.project['stop_freq']/clp.project['start_freq'])) * self.params['rms_time']
        else:
            rms_time = self.params['rms_time']
        rms_samples = round(rms_time * clp.project['sample_rate'])

        if self.params['mode'] != 'peak': # rms levels used for 'rms' and 'crestfactor' modes
            # calculate moving RMS
            residual_rms = np.sqrt(pd.DataFrame(residual*residual).rolling(rms_samples, center=True, min_periods=1).mean())

            # interpolate residual_level at self.out_freqs
            residual_rms = interpolate(response_freqs, np.array(residual_rms)[:,0], self.out_freqs)

            if any(clp.signals['noise']):
                noise_rms = np.sqrt(pd.DataFrame(noise_residual*noise_residual).rolling(rms_samples, center=True, min_periods=1).mean())
                noise_rms = interpolate(response_freqs, np.array(noise_rms)[:,0], self.out_freqs)


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

        # if necessary, calculate moving RMS of raw response signal
        if self.params['mode'] != 'crestfactor':
            if self.params['output']['unit'] in ['dB', '%', '% (IEC method)']: # if peak or rms modes and output is a relative unit
                ref_fr = FrequencyResponse('fr')
                ref_fr.params['output'] = self.params['output'].copy()
                ref_fr.params['output']['unit'] = 'FS'
                ref_fr.params['output']['min_auto'] = False # shouldn't actually have any impact, but set in case of future updates
                ref_fr.params['output']['max_auto'] = False
                ref_fr.measure()
                ref_points = ref_fr.out_points
            else:
                ref_points = None

        if self.params['mode'] == 'peak':
            self.out_points = convert_output_units(residual_peak, ref_points)
            if any(clp.signals['noise']):
                self.out_noise = convert_output_units(noise_peak, ref_points)
        
        if self.params['mode'] == 'rms':
            self.out_points = convert_output_units(residual_rms, ref_points)
            if any(clp.signals['noise']):
                self.out_noise = convert_output_units(noise_rms, ref_points)

        if self.params['mode'] == 'crestfactor':
            self.out_points = convert_output_units(residual_peak, residual_rms)
            if any(clp.signals['noise']):
                self.out_noise = convert_output_units(noise_peak, noise_rms) # does it make sense to calculate a measurement noise floor for crest factor?
    
        
    def init_tab(self):
        super().init_tab()

        # dropdown to select analysis mode
        self.mode = CLParamDropdown('Analysis mode', self.MODES)
        if self.params['mode'] == 'peak':
            self.mode.dropdown.setCurrentIndex(1)
        if self.params['mode'] == 'crestfactor':
            self.mode.dropdown.setCurrentIndex(2)
        self.param_section.addWidget(self.mode)
        def update_mode(index):
            # first, update output units if necessary
            if (index < 2) and (self.params['mode'] == 'crestfactor'): # if changing from crest factor to peak or RMS
                self.output_unit.dropdown.blockSignals(True)
                self.output_unit.dropdown.clear()
                self.output_unit.dropdown.addItems(self.OUTPUT_UNITS)
                output_unit_index = self.output_unit.dropdown.findText(self.params['output']['unit'])
                self.output_unit.dropdown.setCurrentIndex(output_unit_index) # OUTPUT_UNITS is a superset of CREST_FACTOR_UNITS so index should never be -1
                self.output_unit.dropdown.blockSignals(False)
            if (index == 2) and (self.params['mode'] != 'crestfactor'): # if changing from peak or RMS to crest factor
                self.output_unit.dropdown.blockSignals(True)
                self.output_unit.dropdown.clear()
                self.output_unit.dropdown.addItems(self.CREST_FACTOR_UNITS)
                output_unit_index = self.output_unit.dropdown.findText(self.params['output']['unit'])
                if output_unit_index != -1:
                    self.output_unit.dropdown.setCurrentIndex(output_unit_index)
                else:
                    self.params['output']['unit'] = 'dB'
                self.output_unit.dropdown.blockSignals(False)
            # peak and RMS have the same output units, no need to handle the case when switching between the two

            # actually update the mode and recalculate
            match index:
                case 0:
                    self.params['mode'] = 'rms'
                case 1:
                    self.params['mode'] = 'peak'
                case 2:
                    self.params['mode'] = 'crestfactor'
            self.measure()
            self.plot()
        self.mode.update_callback = update_mode

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

        # set maximum harmonic to include in transfer function model
        self.harmonic_range = CLParamNum('Model transfer function up to', self.params['max_harmonic'], 'th harmonic', 1, 20, 'int')
        self.param_section.addWidget(self.harmonic_range)
        def harmonic_suffix(harmonic):
            match harmonic:
                case 1:
                    return 'st harmonic (only fundamental)'
                case 2:
                    return 'nd harmonic'
                case 3:
                    return 'rd harmonic'
                case _:
                    return 'th harmonic'
        self.harmonic_range.unit.setText(harmonic_suffix(self.params['max_harmonic']))
        def update_harmonic_range(new_val):
            self.params['max_harmonic'] = new_val
            self.output_points.update_min_max()
            self.harmonic_range.unit.setText(harmonic_suffix(new_val))
            self.measure()
            self.plot()
        self.harmonic_range.update_callback = update_harmonic_range


        # output parameters
        if self.params['mode'] == 'crestfactor':
            self.output_unit = CLParamDropdown('Units', self.CREST_FACTOR_UNITS, '')
        else:
            self.output_unit = CLParamDropdown('Units', self.OUTPUT_UNITS, '')
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
        return clp.project['stop_freq'] / self.params['max_harmonic']


