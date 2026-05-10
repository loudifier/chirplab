import CLProject as clp
from CLAnalysis import freq_points, interpolate, FS_to_unit, samples_to_ms, ms_to_samples
from scipy.fft import fft, ifft, fftfreq
from scipy.signal.windows import hann
import numpy as np
from CLMeasurements import CLMeasurement

class FrequencyResponse(CLMeasurement):
    measurement_type_name = 'Frequency Response'
    
    WINDOW_MODES = ['raw', 'windowed', 'adaptive']
    MAX_WINDOW_START = 1000 # fixed impulse response window can start up to 1s before t0
    MAX_WINDOW_END = 10000 # IR window can end up to 10s after t0
    OUTPUT_UNITS = ['dBFS', 'dB', 'dBSPL', 'dBV', 'FS', 'Pa', 'V']
    MIN_ADAPTIVE_WINDOW = 1.0 # set a 1ms minimum (maybe make this configurable) to avoid issues with phase/alignment skew, especially at higher frequencies when SNR is usually good anyway
    
    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)

        if len(params)<3: # populate default measurement parameters if none are provided
            # add new keys to existing dict instead of defining new one, so updates will propogate to full project dict and can be easily saved to a project file
            self.params['window_mode'] = 'adaptive' # options are 'raw' for no windowing, 'windowed' for fixed (time-gated) windowing, or 'adaptive' to use an automatically-derived window for each output frequency point
            self.params['window_start'] = 10 # for fixed window, amount of time in ms included before beginning of impulse response
            self.params['fade_in'] = 10 # beginning of fixed window ramps up with a half Hann window of width fade_in (must be <= window_start)
            self.params['window_end'] = 50
            self.params['fade_out'] = 25
            
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dBFS', # all options are absolute units, except for 'dB', which outputs the measured frequency response relative to the absolute response at the specified ref_freq
                'ref_freq': 1000, # used for 'dB' relative output, otherwise ignored
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
            
            
    def measure(self):
        # generate array of output frequency points (adaptive windowing requires out_freqs be generated before calc_fr())
        self.out_freqs = freq_points(self.params['output']['min_freq'], 
                                     self.params['output']['max_freq'],
                                     self.params['output']['num_points'],
                                     self.params['output']['spacing'],
                                     self.params['output']['round_points'])
        
        fr_freqs, fr = self.calc_fr(clp.signals['response'])
        
        # interpolate output points
        self.out_points = interpolate(fr_freqs, fr, self.out_freqs, self.params['output']['spacing']=='linear') # todo: still may not be correct. Verify behavior for linear/log frequency scale *and* linear/log output units
        
        # convert output to desired units
        if self.params['output']['unit'] == 'dB':
            # get the absolute level at the reference frequency
            ref_level = interpolate(fr_freqs, fr, self.params['output']['ref_freq'], self.params['output']['spacing']=='linear')
            self.out_points = 20*np.log10(self.out_points / ref_level)
        else:
            self.out_points = FS_to_unit(self.out_points, self.params['output']['unit'])
        
        
        # check for noise sample and calculate noise floor
        if any(clp.signals['noise']):
            fr_freqs, noise_fr = self.calc_fr(clp.signals['noise'])
            self.out_noise = interpolate(fr_freqs, noise_fr, self.out_freqs, self.params['output']['spacing']=='linear')
            if self.params['output']['unit'] == 'dB':
                self.out_noise = 20*np.log10(self.out_noise / ref_level)
            else:
                self.out_noise = FS_to_unit(self.out_noise, self.params['output']['unit'])
        else:
            self.out_noise = np.zeros(0)
    

    # calculate the frquency response of a given signal, relative to the project stimulus signal, using measurement analysis parameters
    # allows analyzing actual captured signal or noise sample to calculate the measurement and measurement noise floor using the same logic
    def calc_fr(self, input_signal):
        # calculate raw complex frequency response
        fr = fft(input_signal) / fft(clp.signals['stimulus'])
        
        # generate array of center frequencies of fft bins, used for interpolation
        fr_freqs = fftfreq(len(clp.signals['stimulus']), 1/clp.project['sample_rate'])
        # trim to only positive frequencies
        fr_freqs = fr_freqs[1:int(len(fr_freqs)/2)-1] # technically, removes highest point for odd-length inputs, but shouldn't be a problem
        
        if self.params['window_mode'] != 'raw':
            # calcualte raw impulse response for windowed and adaptive modes
            ir = ifft(fr)
            
        # process used by both windowed and adaptive modes
        def calc_windowed_fr(ir, window_start_ms, fade_in_ms, window_end_ms, fade_out_ms):
            # convert windowing times to whole samples
            window_start = ms_to_samples(window_start_ms)
            fade_in = ms_to_samples(fade_in_ms)
            window_end = ms_to_samples(window_end_ms)
            fade_out = ms_to_samples(fade_out_ms)
            
            # construct window
            window = np.zeros(len(ir))
            window[:fade_in] = hann(fade_in*2)[:fade_in]
            window[fade_in:window_start+window_end-fade_out] = np.ones(window_start-fade_in+window_end-fade_out)
            window[window_start+window_end-fade_out:window_start+window_end] = hann(fade_out*2)[fade_out:]
            window = np.roll(window, -window_start)
            
            # apply window to impulse response
            ir = ir * window
            
            # convert windowed impusle response back to frequency response to use for data output
            return fft(ir)
            
        if self.params['window_mode'] == 'windowed':
            fr = calc_windowed_fr(ir, self.params['window_start'], self.params['fade_in'], self.params['window_end'], self.params['fade_out'])
        
        if self.params['window_mode'] == 'adaptive':
            # individual windowed frequency response calculated for each output point
            out_freqs = self.out_freqs
            out_fr = np.zeros(len(out_freqs))
            for freq in range(len(out_freqs)):
                # use a window sized appropriately for the target frequency
                wavelength_ms = 1000 * 1/out_freqs[freq]
                wavelength_ms = max(self.MIN_ADAPTIVE_WINDOW, wavelength_ms)

                adaptive_ir = np.concatenate((ir[:4*ms_to_samples(wavelength_ms)], ir[-2*ms_to_samples(wavelength_ms):])) # zero-pad by 2x before/after window. Results in much smaller windows for faster processing, with reasonable frequency resolution for interpolation

                fr_freqs = fftfreq(len(adaptive_ir), 1/clp.project['sample_rate'])
                fr_freqs = fr_freqs[1:int(len(fr_freqs)/2)-1]

                # calculate windowed frequency response with window size for target frequency
                fr = calc_windowed_fr(adaptive_ir, wavelength_ms, wavelength_ms, 2*wavelength_ms, wavelength_ms)
            
                # trim to positive half of spectrum for interpolation
                fr = fr[1:int(len(fr)/2)-1]
            
                # take magnitude of complex frequency response
                fr = np.abs(fr)
            
                if wavelength_ms > self.MIN_ADAPTIVE_WINDOW:
                    # get target frequency
                    out_fr[freq] = interpolate(fr_freqs, fr, out_freqs[freq])
                else:
                    # remaining frequency output points will use the same window, so get them all
                    out_fr[freq:] = interpolate(fr_freqs, fr, out_freqs[freq:])
                    break

            
            return out_freqs, out_fr
        
        # trim to positive half of spectrum
        fr = fr[1:int(len(fr)/2)-1]
        
        # take magnitude of complex frequency response
        fr = np.abs(fr)
        
        return fr_freqs, fr
        
        
    def init_tab(self):
        from CLGui import CLParamDropdown, CLParamNum, FreqPointsParams, WindowParamsSection
        super().init_tab()

        self.window_mode = CLParamDropdown('Windowing mode', self.WINDOW_MODES, '')
        window_mode_index = self.window_mode.dropdown.findText(self.params['window_mode'])
        if window_mode_index==-1:
            self.params['window_mode'] = 'adaptive'
            window_mode_index = 2 # default to adaptive if the project file is mangled
        self.window_mode.dropdown.setCurrentIndex(window_mode_index)
        self.param_section.addWidget(self.window_mode)
        def update_window_mode(index):
            self.params['window_mode'] = self.WINDOW_MODES[index]
            if self.params['window_mode'] == 'windowed':
                self.window_params.setLocked(False)
            else:
                self.window_params.collapse(animate=self.window_params.isExpanded())
                self.window_params.setLocked(True)
            self.measure()
            self.plot()
        self.window_mode.update_callback = update_window_mode
        
        self.window_params = WindowParamsSection(self.params)
        if self.params['window_mode'] != 'windowed':
            self.window_params.setLocked(True)
        self.param_section.addWidget(self.window_params)
        def update_window_params():
            self.measure()
            self.plot()
        self.window_params.update_callback = update_window_params


        self.output_unit = CLParamDropdown('Units', self.OUTPUT_UNITS, '')
        output_unit_index = self.output_unit.dropdown.findText(self.params['output']['unit'])
        if output_unit_index != -1:
            self.output_unit.dropdown.setCurrentIndex(output_unit_index)
        self.output_section.addWidget(self.output_unit)
        def update_output_unit(index):
            self.params['output']['unit'] = self.OUTPUT_UNITS[index]
            self.ref_freq.setEnabled(self.params['output']['unit'] == 'dB')
            self.measure()
            self.plot()
            self.format_graph()
        self.output_unit.update_callback = update_output_unit

        self.ref_freq = CLParamNum('Normalize to', self.params['output']['ref_freq'], 'Hz', 1, clp.project['sample_rate']/2)
        self.ref_freq.setEnabled(self.params['output']['unit'] == 'dB')
        self.output_section.addWidget(self.ref_freq)
        def update_ref_freq(new_val):
            self.params['output']['ref_freq'] = new_val
            self.measure()
            self.plot()
            self.format_graph()
        self.ref_freq.update_callback = update_ref_freq
        
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
        self.window_params.update_window_params()
        self.output_points.update_min_max()
        self.ref_freq.max = clp.project['sample_rate']/2
        
    def calc_auto_min_freq(self):
        return clp.project['start_freq']
    
    def calc_auto_max_freq(self):
        return min(clp.project['stop_freq'], (clp.project['sample_rate']/2) * 0.9)



            
            
        