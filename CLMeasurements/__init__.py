# individual measurement imports at bottom of file
import numpy as np
from CLGui import CLTab, clear_plot
from qtpy.QtWidgets import QLineEdit
from matplotlib.ticker import LogLocator, EngFormatter


class CLMeasurement():
    measurement_type_name = 'CLMeasurement' # override with individual measurement type. e.g. 'Frequency Response'
    
    def __init__(self, name, params):
        self.name = name
        self.params = params
        
        # add default measurement parameters in individual measurement __init__(). Example for frequency response:
        #if not params: # populate default measurement parameters if none are provided
        #    # add new keys to existing dict instead of defining new one, so updates will propogate to full project dict and can be easily saved to a project file
        #    self.params['window_mode'] = 'windowed'
        #    self.params['window_start'] = 10
        #    self.params['fade_in'] = 10 
        #    self.params['window_end'] = 50
        #    self.params['fade_out'] = 25
        
        #    self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
        #        'unit': 'dBFS',
        #        'num_points': 100,
        #        'scaling': 'log'
        #        }
        
        # assuming most measurement outputs will be output points and measurement noise floor points vs frequency points
        self.out_freqs = np.zeros(0) # frequency points of most recently calculated measurement
        self.out_points = np.zeros(0) # data points of most recently calculated measurement
        self.out_noise = np.zeros(0) # data points of most recently calculated measurement noise floor estimate
            
    def measure(self):
        # Run measurement using current signals, project settings, and measurement parameters, and update measurement data.
        # For most measurements, output frequencies stored in self.out_freq, measurement value for that frequency converted
        # to desired output unit and stored in self.out_data. If a noise sample is present and the measurement is able to 
        # estimate the measurement noise floor the noise floor estimate will be stored in self.out_noise
        pass # override with individual measurement measure() method
        
        
    def init_tab(self):
        self.tab = CLTab()
        
        self.name_box = QLineEdit(self.name)
        self.tab.panel.addWidget(self.name_box)
        
        # add collapsible sections to measurement config panel. Fill out sections for individual measurements
        self.param_section = self.tab.addPanelSection(type(self).measurement_type_name + ' Measurement Parameters')
        # if measurement should have additional sections insert them between measurement params and output params or nest inside measurement params
        self.output_section = self.tab.addPanelSection('Output Settings')
        
    
    def format_graph(self):
        # default graph formatting with title, legend, axis titles, log x scale
        self.tab.graph.axes.set_title(self.name)
        self.tab.graph.axes.set_xscale('log')
        self.tab.graph.axes.xaxis.set_major_locator(LogLocator(subs=[1.0, 2.0, 5.0])) # 1-2-5 ticks along x axis
        self.tab.graph.axes.xaxis.set_major_formatter(EngFormatter()) # 100>"100", 2000>"2k", etc.
    
    def plot(self):
        # basic plot, could be much more complex for different measurement types (like waterfalls)
        
        clear_plot(self.tab.graph.axes)
        
        self.tab.graph.axes.plot(self.out_freqs, self.out_points, label=self.measurement_type_name)
        if any(self.out_noise):
            self.tab.graph.axes.plot(self.out_freqs, self.out_noise, label='Noise Floor', color='gray')
        self.tab.graph.axes.legend()
        self.tab.graph.axes.set_ylabel(self.params['output']['unit'])
        self.tab.graph.axes.set_xlabel('Frequency (Hz)') # majority of measurements assume output data vs frequency
        self.tab.graph.draw()

# imports in __init__.py make measurements available in other code via `import CLMeasurements`, etc.
from CLMeasurements.frequency_response import FrequencyResponse
from CLMeasurements.harmonic_distortion import HarmonicDistortion