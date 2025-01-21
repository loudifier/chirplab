import CLProject as clp
from CLGui import CLParameter
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal.windows import hann
import numpy as np
from CLMeasurements import CLMeasurement


class FrequencyResponse(CLMeasurement):
    measurement_type_name = 'Frequency Response'
    
    def __init__(self, name, params):
        super().__init__(name, params)

        if not params: # populate default measurement parameters if none are provided
            # add new keys to existing dict instead of defining new one, so updates will propogate to full project dict and can be easily saved to a project file
            self.params['window_mode'] = 'windowed' # options are 'raw' for no windowing, 'windowed' for fixed (time-gated) windowing, or 'adaptive' to use an automatically-derived window for each output frequency point
            self.params['window_start'] = 10 # for fixed window, amount of time in ms included before beginning of impulse response
            self.params['fade_in'] = 10 # beginning of fixed window ramps up with a half Hann window of width fade_in (must be <= window_start)
            self.params['window_end'] = 50
            self.params['fade_out'] = 25
            
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dBFS',
                'num_points': 100,
                'scaling': 'log'
                }
            
            
    def measure(self):
        fr_freqs, fr = self.calc_fr(clp.signals['response'])

        # generate array of output frequency points
        if self.params['output']['scaling'] == 'log':
            self.out_freqs = np.geomspace(clp.project['start_freq'], clp.project['stop_freq'], self.params['output']['num_points'])
        else:
            self.out_freqs = np.linspace(clp.project['start_freq'], clp.project['stop_freq'], self.params['output']['num_points'])
        
        
        # interpolate output points
        print('todo: work out lin/log interpolation')
        # pretty sure you should take the log of the in/out frequencies before interpolation. Might also depend on whether output units are lin/log. Probably fine for reasonable chirp lengths/resolution
        #if self.params['output']['scaling'] == 'log':
        self.out_points = np.interp(self.out_freqs, fr_freqs, fr)
        
        # convert output to desired units
        if self.params['output']['unit'] == 'dBFS':
            self.out_points = 20*np.log10(self.out_points)
        
        
        # check for noise sample and calculate noise floor
        if any(clp.signals['noise']):
            fr_freqs, noise_fr = self.calc_fr(clp.signals['noise'])
            self.out_noise = np.interp(self.out_freqs, fr_freqs, noise_fr)
            if self.params['output']['unit'] == 'dBFS':
                self.out_noise = 20*np.log10(self.out_noise)
        else:
            self.out_noise = np.zeros(0)
    

    # calculate the frquency response of a given signal, relative to the project stimulus signal, using measurement analysis parameters
    # allows analyzing actual captured signal or noise sample to calculate the measurement and measurement noise floor using the same logic
    def calc_fr(self, input_signal):
        # calculate raw complex frequency response
        fr = fft(input_signal) / fft(clp.signals['stimulus'])
        
        # generate IR, apply window, and calculate windowed FR
        if self.params['window_mode'] == 'windowed':
            # calcualte raw impulse response
            ir = ifft(fr)
            
            # calculate windowing times in whole samples
            window_start = round((self.params['window_start'] / 1000) * clp.project['sample_rate'])
            fade_in = round((self.params['fade_in'] / 1000) * clp.project['sample_rate'])
            window_end = round((self.params['window_end'] / 1000) * clp.project['sample_rate'])
            fade_out = round((self.params['fade_out'] / 1000) * clp.project['sample_rate'])
            
            # construct window
            window = np.zeros(len(ir))
            window[:fade_in] = hann(fade_in*2)[:fade_in]
            window[fade_in:window_start+window_end-fade_out] = np.ones(window_start-fade_in+window_end-fade_out)
            window[window_start+window_end-fade_out:window_start+window_end] = hann(fade_out*2)[fade_out:]
            window = np.roll(window, -window_start)
            
            # apply window to impulse response
            ir = ir * window
            
            # convert windowed impusle response back to frequency response to use for data output
            fr = fft(ir)
            
        elif self.params['window_mode'] == 'adaptive':
            pass
        
        
        # generate array of center frequencies of fft bins
        fr_freqs = fftfreq(len(clp.signals['stimulus']), 1/clp.project['sample_rate'])

        # trim fft fr and freqs to positive half of spectrum. Easier to interpolate output points
        fr = fr[1:int(len(fr)/2)-1] # technically, removes highest point for odd-length inputs, but shouldn't be a problem
        fr_freqs = fr_freqs[1:int(len(fr_freqs)/2)-1]
        
        # take magnitude of complex frequency response
        fr = np.abs(fr)
        
        return fr_freqs, fr
        
        
    def init_tab(self):
        super().init_tab()

        self.window_mode = CLParameter('Windowing mode', self.params['window_mode'], '')
        self.param_section.addWidget(self.window_mode)
        

        self.output_unit = CLParameter('Units', self.params['output']['unit'], '')
        self.output_section.addWidget(self.output_unit)
    