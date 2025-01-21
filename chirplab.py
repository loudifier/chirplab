from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QSplitter, QTextEdit, QComboBox
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
import numpy as np
from scipy.io import wavfile
import matplotlib.pyplot as plt
import sys
import CLMeasurements
from CLGui import CLTab, ChirpTab, CLParameter

CHIRPLAB_VERSION = 0


def main():
    if len(sys.argv) < 2:
        # chirplab started without any arguments. Lauch GUI with a default New Project
        # project dictionary containing parameters of log chirp used for signal generation and analysis, signal input and output, etc
        project = {
            'chirplab_version': CHIRPLAB_VERSION, # when loading project files from older versions of chirplab, the project may be able to be upgraded for compatibility with current version
            'project_name': 'New Project',
            
            # chirp parameters
            'start_freq': 100, # chirp starting frequency in Hz
            'stop_freq': 20000,
            'chirp_length': 1.0, # length in seconds
            
            # chirp analysis parameters
            'pre_sweep': 0.05, # silence before start of chirp included in analysis window, length in seconds
            'post_sweep': 0.05,
            'sample_rate': 48000, # sample rate in Hz used for all analysis
            
            # parameters of stimulus file or audio output device
            'output': {
                'mode': 'file', # 'file' or 'device'
                'sample_rate': 48000,
                'bit_depth': 24,
                'num_channels': 1,
                'channel':'all', # which channel chirp stimulus is written to (for files) or output to (for playback devices). 'all' to replicate chirp on every output channel
                'amplitude': 0.1, # amplitude in FS (e.g. 0.1FS = -20dBFS)
                'pre_sweep': 0.5, # silence to include before/after chirp. Only used for stimulus generation, independent from analysis pre/post_sweep
                'post_sweep': 0.5,
                'include_silence': True, # preprend output signal with silence of length pre_sweep + chirp_length + post_sweep for measurement noise floor estimation
                },
            
            # parameters of input file containing recording of chirp response or audio input device to record response
            'input': {
                'mode': 'file',
                'channel': 1, # which channel to use from input file or capture device
                'file': 'response.wav', # input file path
                },
            
            # list of measurements
            'measurements': [
                {
                    'name': 'Frequency Response', # user-defined measurement name
                    'type': 'FrequencyResponse', # measurement type matching a class name from the measurements module
                    'params': {} # if empty params will be generated from default in measurement class
                    } 
                ]
            
            }
    else:
        # parse input arguments
        # first argument is chirplab project file
        # -b for batch mode (command-line) processing
        # etc
        pass
        
    # initialize measurements
    measurements = []
    for measurement in project['measurements']:
        Measurement = getattr(CLMeasurements, measurement['type']) # dynamically invoke measurement class from measurement type string
        measurements.append(Measurement(measurement['name'], measurement['params'], project))
    
    
    app = QApplication([])
    screen_size = app.screens()[0].size()
    
    window = MainWindow(project, measurements)
    window.resize(int(screen_size.width()*0.75), int(screen_size.height()*0.75))
    window.show()
    
    app.exec()
    
    
    

class MainWindow(QMainWindow):
    def __init__(self, project, measurements):
        super().__init__()
        self.project = project
        self.measurements = measurements
        self.setWindowTitle('Chirplab')
        
        # main GUI structure for navigating between chirp parameters/IO and measurements
        tabs = QTabWidget()
        
        # First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
        chirp_tab = ChirpTab(self.project)
        tabs.addTab(chirp_tab,'Chirp Stimulus/Response')

        # Additional tab for each measurement
        for measurement in measurements:
            tabs.addTab(measurement.tab, measurement.name)
        
        
        layout = QGridLayout() # base layout. Only 0,0 used
        layout.addWidget(tabs, 0,0)
        widget = QWidget() # Layout can't be applied directly to QMainWindow, need a base QWidget
        widget.setLayout(layout)
        self.setCentralWidget(widget)
 
        
    
        

 
    
main()