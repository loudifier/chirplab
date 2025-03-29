# individual measurement imports at bottom of file
import CLProject as clp
import numpy as np
from CLGui import CLTab, QCollapsible, QHSeparator
from qtpy.QtWidgets import QLineEdit
import pyqtgraph as pg
from pathvalidate import is_valid_filename
from importlib import import_module


class CLMeasurement():
    measurement_type_name = 'CLMeasurement' # override with individual measurement type. e.g. 'Frequency Response'
    
    def __init__(self, name, params=None):
        if params is None:
            self.params = {}
        else:
            self.params = params
        self.params['name'] = name
        self.params['type'] = 'CLMeasurement'
        
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
        
        self.name_box = QLineEdit(self.params['name'])
        self.tab.panel.addWidget(self.name_box)
        self.name_box.last_value = self.params['name']
        def update_name():
            new_name = self.name_box.text().strip()
            if not is_valid_measurement_name(new_name):
                self.name_box.setText(self.name_box.last_value)
                return
                
            self.params['name'] = new_name
            self.format_graph()
            self.name_box.last_value = self.params['name']
            
            # updating the tab title is a little sketchy... come back later to see if there is a more elegant soltuion?
            tab_group = self.tab.parent().parent()
            tab_index = tab_group.indexOf(self.tab)
            tab_group.setTabText(tab_index, self.params['name'])
        self.name_box.editingFinished.connect(update_name)
        
        # add collapsible sections to measurement config panel. Fill out sections for individual measurements
        self.param_section = QCollapsible(type(self).measurement_type_name + ' Measurement Parameters')
        self.param_section.expand()
        self.tab.panel.addWidget(self.param_section)
        self.tab.panel.addWidget(QHSeparator())
        # if measurement should have additional sections insert them between measurement params and output params or nest inside measurement params
        self.output_section = QCollapsible('Output Settings')
        self.output_section.expand()
        self.tab.panel.addWidget(self.output_section)
        
    
    def update_tab(self):
        # Provide a hook for upstream GUI elements to propogate updates to measurement tabs
        # i.e. update frequency response window sample counts when analysis sample rate is changed
        pass
        
        
    def format_graph(self):
        # default graph formatting with title, legend, axis titles, log x scale
        self.tab.graph.setTitle(self.params['name'])
        self.tab.graph.setLogMode(True, False) # default to log frequency scale
        self.tab.graph.setLabel('bottom', 'Frequency (Hz)')
        self.tab.graph.setLabel('left', self.params['output']['unit'])
        #self.tab.graph.getAxis('bottom').enableAutoSIPrefix(True) # consider using pyqtgraph's unit system. Manually constructing axis labels for now

    
    def plot(self):
        # basic plot, could be much more complex for different measurement types (like waterfalls)
        
        self.tab.graph.clear()
        
        plot_pen = pg.mkPen(color=clp.PLOT_COLORS[0], width=clp.PLOT_PEN_WIDTH)
        self.tab.graph.plot(self.out_freqs, self.out_points, name = self.measurement_type_name, pen=plot_pen) # todo: do something different when plotting a single point (pyqtgraph falls on its face otherwise)
        
        if any(self.out_noise):
            noise_pen = pg.mkPen(color=clp.NOISE_COLOR, width=clp.PLOT_PEN_WIDTH)
            self.tab.graph.plot(self.out_freqs, self.out_noise, name='Noise Floor', pen=noise_pen)#, color='gray')

        
# list of the class names of all measurement types that are available
MEASUREMENT_TYPES = ['FrequencyResponse', 'HarmonicDistortion', 'PhaseResponse', 'GroupDelay', 'TrackingFilter', 'ImpulsiveDistortion']

# imports in __init__.py make measurements available in other code via `from CLMeasurements import <measurement class>`, etc.
for measurement in MEASUREMENT_TYPES:
    module = import_module('CLMeasurements.'+measurement)
    globals()[measurement] = getattr(module, measurement)
    


def init_measurements():
    # builds (or rebuilds) a new set of measurement objects from current clp.project
    clp.measurements = []
    for measurement in clp.project['measurements']:
        Measurement = globals()[measurement['type']] # dynamically invoke measurement class from measurement type string
        clp.measurements.append(Measurement(measurement['name'], measurement))
        
def is_valid_measurement_name(name):
    return is_valid_filename(name) # measurement name likely used for CLI output. Any other restrictions?