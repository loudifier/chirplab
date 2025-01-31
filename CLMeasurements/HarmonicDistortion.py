import CLProject as clp
from CLAnalysis import logchirp, chirp_freq_to_time, freq_points, interpolate
from CLGui import CLParameter, CLParamNum, CLParamDropdown, FreqPointsParams
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal.windows import hann
import numpy as np
from CLMeasurements import CLMeasurement, FrequencyResponse
#from CLMeasurements.FrequencyResponse import FrequencyResponse

# Harmonic Distortion analysis based on Farina papers. https://www.researchgate.net/publication/2456363_Simultaneous_Measurement_of_Impulse_Response_and_Distortion_With_a_Swept-Sine_Technique

class HarmonicDistortion(CLMeasurement):
    measurement_type_name = 'Harmonic Distortion'
    
    OUTPUT_UNITS = ['dB', '%', '% (IEC method)', 'dBFS', 'FS']
    
    def __init__(self, name, params):
        super().__init__(name, params)

        if not params: # default measurement parameters
            self.params['start_harmonic'] = 2 # default to low order THD (H2:H7)
            self.params['stop_harmonic'] = 7
            self.params['window_start'] = 0.1 # windowing parameters similar to frequency response windowing, but windows are centered on harmonic impulses, numbers are expressed in proportion of time to previous/next harmonic impulse
            self.params['fade_in'] = 0.1      # e.g. for H2 impulse arriving 10ms after H3 impulse, fade_in=0.1 results in harmonic window starting 1ms before H2 harmonic impulse
            self.params['window_end'] = 0.9   # fade_in/out must be <= window_start/end, respectively
            self.params['fade_out'] = 0.5     # window_start + window_end should be <1 to avoid overlap between harmonic impulse windows
            
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dB', # options are 'dB' or '%' relative to fundamental
                'min_freq': 20,
                'min_auto': True, # min_freq ignored and updated if True
                'max_freq': 10000,
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
        thd_freqs, thd = self.calc_thd(clp.signals['response'])

        # generate array of output frequency points
        self.out_freqs = freq_points(self.params['output']['min_freq'], 
                                     self.params['output']['max_freq'],
                                     self.params['output']['num_points'],
                                     self.params['output']['spacing'],
                                     self.params['output']['round_points'])
        
        
        # interpolate output points
        self.out_points = interpolate(thd_freqs, thd, self.out_freqs, self.params['output']['spacing']=='linear')
        
        # assume most output units will want a fundamental frequency response reference
        ref_fr = FrequencyResponse('fr',{})
        ref_fr.params['output'] = self.params['output'].copy()
        ref_fr.params['output']['unit'] = 'fs'
        ref_fr.params['output']['min_auto'] = False # shouldn't actually have any impact, but set in case of future updates
        ref_fr.params['output']['max_auto'] = False
        ref_fr.measure()
        
        # convert output to desired units
        def convert_output_units(fs_points):
            match self.params['output']['unit']:
                case 'dB':
                    return 20*np.log(fs_points / ref_fr.out_points)
                case '%':
                    return 100 * fs_points / ref_fr.out_points
                case '% (IEC method)':
                    return 100 * fs_points / (ref_fr.out_points + fs_points)
                case 'dBFS':
                    return 20*np.log10(fs_points)
                case _: # 'FS'
                    return fs_points
        self.out_points = convert_output_units(self.out_points)
        
        
        # check for noise sample and calculate noise floor
        if any(clp.signals['noise']):
            fr_freqs, noise_floor = self.calc_thd(clp.signals['noise'])
            self.out_noise = interpolate(fr_freqs, noise_floor, self.out_freqs, self.params['output']['spacing']=='linear')
            self.out_noise = convert_output_units(self.out_noise)
        else:
            self.out_noise = np.zeros(0)
        
        
    def calc_thd(self, input_signal):
        # geneate a reference chirp that extends to Nyquist. Otherwise, only analysis of chirps that extend up to or very near Nyquist will be accurate
        thd_chirp_length = chirp_freq_to_time(clp.project['start_freq'], clp.project['stop_freq'], clp.project['chirp_length'], clp.project['sample_rate']/2)
        stimulus = np.concatenate([
            np.zeros(round(clp.project['pre_sweep']*clp.project['sample_rate'])),
            logchirp(clp.project['start_freq'], clp.project['sample_rate']/2, thd_chirp_length, clp.project['sample_rate'])])
        
        # pad stimulus or response to be the same length
        if len(stimulus) < len(input_signal):
            stimulus = np.concatenate([stimulus, np.zeros(len(input_signal) - len(stimulus))])
        else:
            input_signal = np.concatenate([input_signal, np.zeros(len(stimulus) - len(input_signal))])
        
        # calculate raw complex frequency response and IR
        fr = fft(input_signal) / fft(stimulus)
        ir = ifft(fr)
        
        # generate array of center frequencies of fft bins
        fr_freqs = fftfreq(len(stimulus), 1/clp.project['sample_rate'])
        fr_freqs = fr_freqs[1:int(len(fr_freqs)/2)-1] # trim to positive frequencies
        
        # initialize blank total harmonic power spectrum
        total_harmonic_power = np.zeros(len(fr_freqs))
        
        # loop through harmonics
        for harmonic in range(self.params['start_harmonic'], self.params['stop_harmonic']+1):
            # generate harmonic window
            harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic)
            prev_harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic+1) # next harmonic *number*, previous in terms of *arrival time*. Used to calculate window_start
            next_harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic-1)
        
            fade_in = round(self.params['fade_in']*(harmonic_time-prev_harmonic_time)*clp.project['sample_rate'])
            window_start = round(self.params['window_start']*(harmonic_time-prev_harmonic_time)*clp.project['sample_rate'])
            fade_out = round(self.params['fade_out']*(next_harmonic_time-harmonic_time)*clp.project['sample_rate'])
            window_end = round(self.params['window_end']*(next_harmonic_time-harmonic_time)*clp.project['sample_rate'])
            
            harmonic_window = np.zeros(len(ir))
            harmonic_window[:fade_in] = hann(fade_in*2)[:fade_in]
            harmonic_window[fade_in:window_start+window_end-fade_out] = np.ones(window_start-fade_in+window_end-fade_out)
            harmonic_window[window_start+window_end-fade_out:window_start+window_end] = hann(fade_out*2)[fade_out:]
            harmonic_window = np.roll(harmonic_window, round(harmonic_time*clp.project['sample_rate'])-window_start)
            
            # apply harmonic window to IR
            harmonic_ir = ir * harmonic_window
            
            # get harmonic spectrum
            harmonic_spectrum = fft(harmonic_ir)
            harmonic_spectrum = harmonic_spectrum[1:int(len(harmonic_spectrum)/2)-1]

            # take magnitude of complex spectrum
            harmonic_spectrum = np.abs(harmonic_spectrum)

            # apply frequncy scaling/interpolation
            harmonic_spectrum = np.interp(fr_freqs, fr_freqs/harmonic, harmonic_spectrum)

            # add single harmonic power to total harmonic power
            total_harmonic_power = total_harmonic_power + np.square(harmonic_spectrum)
        
        
        # take square root of harmonic power to complete power sum
        total_harmonic_power = np.sqrt(total_harmonic_power)
        
        return fr_freqs, total_harmonic_power
    
    
        
    def init_tab(self):
        super().init_tab()

        self.start_harmonic = CLParamNum('Lowest harmonic', self.params['start_harmonic'], '', 2, 40, 'int')
        self.param_section.addWidget(self.start_harmonic)
        
        self.stop_harmonic = CLParamNum('Highest harmonic', self.params['stop_harmonic'], '', 2, 40, 'int')
        self.param_section.addWidget(self.stop_harmonic)
        
        def update_harmonics(val):
            if self.start_harmonic.value > self.stop_harmonic.value:
                self.start_harmonic.revert()
                self.stop_harmonic.revert()
            else:
                self.params['start_harmonic'] = self.start_harmonic.value
                self.params['stop_harmonic'] = self.stop_harmonic.value
                self.measure()
                self.plot()
        self.start_harmonic.update_callback = update_harmonics
        self.stop_harmonic.update_callback = update_harmonics
        
        
        
        self.output_unit = CLParamDropdown('Units', [unit for unit in self.OUTPUT_UNITS], '')
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
        # highest chirp frequency or 90% of Nyquist divided by lowest harmonic
        return min(clp.project['stop_freq'], ((clp.project['sample_rate']/2) * 0.9) / self.params['start_harmonic']) 
        
        
        
def harmonic_impulse_time(chirp_length, start_freq, stop_freq, harmonic):
    # calculates and returns the arrival time in of a harmonic impulse response, relative to the t=0 of the fundamental impulse response
    return -1 * chirp_length * (np.log(harmonic) / np.log(stop_freq/start_freq));
    