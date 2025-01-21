import CLProject as clp
from CLGui import CLTab, CLParameter
from qtpy.QtWidgets import QLineEdit
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal.windows import hann
import numpy as np
from CLMeasurements.frequency_response import FrequencyResponse
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, EngFormatter

# Harmonic Distortion analysis based on Farina papers. https://www.researchgate.net/publication/2456363_Simultaneous_Measurement_of_Impulse_Response_and_Distortion_With_a_Swept-Sine_Technique

class HarmonicDistortion:
    def __init__(self, name, params):
        self.name = name
        self.params = params
        if not params: # default measurement parameters
            self.params['start_harmonic'] = 2 # default to low order THD (H2:H7)
            self.params['stop_harmonic'] = 7
            self.params['window_start'] = 0.1 # windowing parameters similar to frequency response windowing, but windows are centered on harmonic impulses, numbers are expressed in proportion of time to previous/next harmonic impulse
            self.params['fade_in'] = 0.1      # e.g. for H2 impulse arriving 10ms after H3 impulse, fade_in=0.1 results in harmonic window starting 1ms before H2 harmonic impulse
            self.params['window_end'] = 0.9   # fade_in/out must be <= window_start/end, respectively
            self.params['fade_out'] = 0.5     # window_start + window_end should be <1 to avoid overlap between harmonic impulse windows
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dB', # options are 'dB' or '%' relative to fundamental
                'num_points': 100,
                'scaling': 'log'
                # default output frequency range from chirp start freq to chirp stop freq/lowest harmonic
                }
            
        self.out_freqs = np.zeros(0) # frequency points of most recently calculated measurement
        self.out_points = np.zeros(0) # data points of most recently calculated measurement
        self.out_noise = np.zeros(0) # data points of most recently calculated measurement noise floor estimate
            
    def measure(self):
        # calculate raw complex frequency response and IR
        fr = fft(clp.signals['response']) / fft(clp.signals['stimulus'])
        ir = ifft(fr)
        
        # generate array of center frequencies of fft bins
        fr_freqs = fftfreq(len(clp.signals['stimulus']), 1/clp.project['sample_rate'])
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

        # generate array of output frequency points
        if self.params['output']['scaling'] == 'log':
            self.out_freqs = np.geomspace(clp.project['start_freq'], clp.project['stop_freq'], self.params['output']['num_points'])
        else:
            self.out_freqs = np.linspace(clp.project['start_freq'], clp.project['stop_freq'], self.params['output']['num_points'])
        
        
        # interpolate output points
        self.out_points = np.interp(self.out_freqs, fr_freqs, total_harmonic_power)
        
        # convert output to desired units
        if self.params['output']['unit'] == 'dB':
            ref_fr = FrequencyResponse('fr',{})
            ref_fr.params['output']['unit'] = 'fs'
            ref_fr.measure()
            self.out_points = 20*np.log10(self.out_points / ref_fr.out_points)
        
        
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
        
    # default graph formatting with title, legend, axis titles, log x scale
    def format_graph(self):
        self.tab.graph.axes.set_title(self.name)
        self.tab.graph.axes.set_xscale('log')
        self.tab.graph.axes.xaxis.set_major_locator(LogLocator(subs=[1.0, 2.0, 5.0])) # 1-2-5 ticks along x axis
        self.tab.graph.axes.xaxis.set_major_formatter(EngFormatter()) # 100>"100", 2000>"2k", etc.
        
    def plot(self):
        # basic plot, could be much more complex for different measurement types (like waterfalls)
        self.tab.graph.axes.plot(self.out_freqs, self.out_points)
        self.tab.graph.draw()
        
        
def harmonic_impulse_time(chirp_length, start_freq, stop_freq, harmonic):
    # calculates and returns the arrival time in of a harmonic impulse response, relative to the t=0 of the fundamental impulse response
    return -1 * chirp_length * (np.log(harmonic) / np.log(stop_freq/start_freq));
    