import CLProject as clp
from CLGui import CLTab, CLParameter
from qtpy.QtWidgets import QLineEdit
from scipy.fftpack import fft, ifft, fftfreq
import numpy as np

class FrequencyResponse:
    def __init__(self, name, params):
        self.name = name
        self.params = params
        if not params: # populate default measurement parameters if none are provided
            # add new keys to existing dict instead of defining new one, so updates will propogate to full project dict and can be easily saved to a project file
            self.params['window_mode'] = 'raw' # options are 'raw' for no windowing, 'windowed' for fixed (time-gated) windowing, or 'adaptive' to use an automatically-derived window for each output frequency point
            self.params['window_start'] = 10, # for fixed window, amount of time in ms included before beginning of impulse response
            self.params['fade_in'] = 10, # beginning of fixed window ramps up with a half Hann window of width fade_in (must be <= window_start)
            self.params['window_end'] = 50,
            self.params['fade_out'] = 25,
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dBFS',
                'num_points': 100,
                'scaling': 'log'
                }
            
            self.out_freqs = 0 # frequency points of most recently calculated measurement
            self.out_points = 0 # data points of most recently calculated measurement
            
    def measure(self):
        # run measurement using current signals, project settings, and measurement parameters, and return measurement data
        # output data is a 2D numpy array with frequencies in the first column, measurement value for that frequency in the
        # second column. If a noise sample is present and the measurement is able to estimate measurement noise floor the
        # noise floor estimate will be output in a third column
        
        # calculate raw complex frequency response
        fr = fft(clp.signals['response']) / fft(clp.signals['stimulus'])
        
        # generate IR, apply window, and calculate windowed FR
        if self.params['window_mode'] == 'windowed':
            pass
        elif self.params['window_mode'] == 'adaptive':
            pass
        
        
        # generate array of center frequencies of fft bins
        fr_freqs = fftfreq(len(clp.signals['stimulus']), 1/clp.project['sample_rate'])

        # generate array of output frequency points
        if self.params['output']['scaling'] == 'log':
            self.out_freqs = np.geomspace(clp.project['start_freq'], clp.project['stop_freq'], self.params['output']['num_points'])
        else:
            self.out_freqs = np.linspace(clp.project['start_freq'], clp.project['stop_freq'], self.params['output']['num_points'])
        
        # trim fft fr and freqs to positive half of spectrum. Easier to interpolate output points
        fr = fr[1:int(len(fr)/2)-1] # technically, removes highest point for odd-length inputs, but shouldn't be a problem
        fr_freqs = fr_freqs[1:int(len(fr_freqs)/2)-1]
        
        # interpolate output points
        print('todo: work out lin/log interpolation')
        # pretty sure you should take the log of the in/out frequencies before interpolation. Might also depend on whether output units are lin/log. Probably fine for reasonable chirp lengths/resolution
        #if self.params['output']['scaling'] == 'log':
        self.out_points = np.interp(self.out_freqs, fr_freqs, fr)
        
        # convert output to desired units
        if self.params['output']['unit'] == 'dBFS':
            self.out_points = 20*np.log10(self.out_points)
        
        
        # check for noise sample and calculate noise floor
        
        
        
    def init_tab(self):
        self.tab = CLTab()
        
        self.name_box = QLineEdit(self.name)
        self.tab.panel.addWidget(self.name_box)
        
        self.param_section = self.tab.addPanelSection('Frequency Response Measurement Parameters')
        
        self.window_mode = CLParameter('Windowing mode', self.params['window_mode'], '')
        self.param_section.addWidget(self.window_mode)
        
        self.output_section = self.tab.addPanelSection('Output Settings')
        
        self.output_unit = CLParameter('Units', self.params['output']['unit'], '')
        self.output_section.addWidget(self.output_unit)
        
        # run initial measurement and plot results
        self.measure()
        self.tab.graph.axes.plot(self.out_freqs, self.out_points)
        self.tab.graph.draw()
        