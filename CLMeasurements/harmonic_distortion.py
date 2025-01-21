import CLProject as clp
from CLGui import CLTab, CLParameter
from qtpy.QtWidgets import QLineEdit
from scipy.fftpack import fft, ifft, fftfreq
import numpy as np

# Harmonic Distortion analysis based on Farina papers. https://www.researchgate.net/publication/2456363_Simultaneous_Measurement_of_Impulse_Response_and_Distortion_With_a_Swept-Sine_Technique

class HarmonicDistortion:
    def __init__(self, name, params):
        self.name = name
        self.params = params
        if not params: # default measurement parameters
            self.params['start_harmonic'] = 2 # default to low order THD (H2:H7)
            self.params['stop_harmonic'] = 7
            self.params['window_start'] = 10, # windowing parameters similar to frequency response windowing, but windows are centered on harmonic impulses, numbers are expressed in proportion of time to previous/next harmonic impulse
            self.params['fade_in'] = 10, # e.g. for H2 impulse arriving 10ms after H3 impulse, fade_in=0.1 results in harmonic window starting 1ms before H2 harmonic impulse
            self.params['window_end'] = 50, # fade_in/out must be <= window_start/end, respectively
            self.params['fade_out'] = 25,
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dB', # options are 'dB' or '%' relative to fundamental
                'num_points': 100,
                'scaling': 'log'
                # default output frequency range from chirp start freq to chirp stop freq/lowest harmonic
                }
            
            self.out_freqs = 0 # frequency points of most recently calculated measurement
            self.out_points = 0 # data points of most recently calculated measurement
            
    def measure(self):
        # calculate raw complex frequency response and IR
        fr = fft(clp.signals['response']) / fft(clp.signals['stimulus'])
        ir = ifft(fr)
        
        # generate array of center frequencies of fft bins
        fr_freqs = fftfreq(len(clp.signals['stimulus']), 1/clp.project['sample_rate'])
        
        # initialize blank total harmonic power spectrum
        total_harmonic_power = np.zeros(len(fr))
        
        # loop through harmonics
        for harmonic in range(self.params['start_harmonic'], self.params['stop_harmonic']+1):
            # generate harmonic window
            harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic)
            prev_harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic-1)
            next_harmonic_time = harmonic_impulse_time(clp.project['chirp_length'], clp.project['start_freq'], clp.project['stop_freq'], harmonic+1)
        
            
        #   apply harmonic window to IR
        #   get harmonic power spectrum (fft(ir))
        #   apply frequncy scaling/interpolation
        #   add single harmonic power to total harmonic power
        
        
        
        

        # generate array of output frequency points
        if self.params['output']['scaling'] == 'log':
            self.out_freqs = np.geomspace(clp.project['start_freq'], clp.project['stop_freq']/self.params['start_harmonic'], self.params['output']['num_points'])
        else:
            self.out_freqs = np.linspace(clp.project['start_freq'], clp.project['stop_freq']/self.params['start_harmonic'], self.params['output']['num_points'])
        
        
        # interpolate output points
        #self.out_points = np.interp(self.out_freqs, fr_freqs, total_harmonic_power)
        
        # convert output to desired units
        if self.params['output']['unit'] == 'dB':
            pass # generate a new FrequencyResponse measurement and evaluate it using default parameters to get the fundamental frequency response reference
        
        
        # check for noise sample and calculate noise floor
        
        
        
    def init_tab(self):
        self.tab = CLTab()
        
        self.name_box = QLineEdit(self.name)
        self.tab.panel.addWidget(self.name_box)
        
        self.param_section = self.tab.addPanelSection('Harmmonic Distortion Measurement Parameters')
        
        #self.window_mode = CLParameter('Windowing mode', self.params['window_mode'], '')
        #self.param_section.addWidget(self.window_mode)
        
        #self.output_section = self.tab.addPanelSection('Output Settings')
        
        #self.output_unit = CLParameter('Units', self.params['output']['unit'], '')
        #self.output_section.addWidget(self.output_unit)
        
        # run initial measurement and plot results
        self.measure()
        #self.tab.graph.axes.plot(self.out_freqs, self.out_points)
        #self.tab.graph.draw()
        
        
def harmonic_impulse_time(chirp_length, start_freq, stop_freq, harmonic):
    # calculates and returns the arrival time in of a harmonic impulse response, relative to the t=0 of the fundamental impulse response
    return -1 * chirp_length * (np.log(harmonic) / np.log(stop_freq/start_freq));
    