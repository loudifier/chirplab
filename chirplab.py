from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QSplitter, QTextEdit
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
import matplotlib.pyplot as plt
import sys
from measurements import FrequencyResponse
from gui import CLTab, CLParameter

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
                'pre_sweep': 0.5, # silence to include before/after chirp, independent from analysis pre/post_sweep
                'post_sweep': 0.5,
                'include_silence': True, # preprend output signal with silence of length pre_sweep + chirp_length + post_sweep for measurement noise floor estimation
                },
            
            # parameters of input file containing recording of chirp response or audio input device to record response
            'input': {
                'mode': 'file',
                'channel': 1, # which channel to use from input file or capture device
                'file': '', # input file path
                },
            
            }
    else:
        # parse input arguments
        # first argument is chirplab project file
        # -b for batch mode (command-line) processing
        # etc
        pass
        
        
    
    
    app = QApplication([])
    screen_size = app.screens()[0].size()
    
    window = MainWindow(project)
    window.resize(int(screen_size.width()*0.75), int(screen_size.height()*0.75))
    window.show()
    
    app.exec()
    
    
    

class MainWindow(QMainWindow):
    def __init__(self, project):
        super().__init__()
        self.project = project
        self.setWindowTitle('Chirplab')
        
        # main GUI structure for navigating between chirp parameters/IO and measurements
        tabs = QTabWidget()
        
        # First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
        chirp_tab = CLTab(self.project)
        tabs.addTab(chirp_tab,'Chirp Stimulus/Response')
        
        chirp_params = chirp_tab.addPanelSection('Chirp Parameters')
        start_freq = CLParameter('Start Freq', self.project['start_freq'], 'Hz')
        chirp_params.addWidget(start_freq)
        stop_freq = CLParameter('Stop Freq', self.project['stop_freq'], 'Hz')
        chirp_params.addWidget(stop_freq)
        chirp_length = CLParameter('Chirp Length', self.project['chirp_length'], 'Sec')
        chirp_params.addWidget(chirp_length)
        
        
        output_params = chirp_tab.addPanelSection('Output')
        input_params = chirp_tab.addPanelSection('Input')
        
        
        
        
        
        layout = QGridLayout() # base layout. Only 0,0 used
        layout.addWidget(tabs, 0,0)
        widget = QWidget() # Layout can't be applied directly to QMainWindow, need a base QWidget
        widget.setLayout(layout)
        self.setCentralWidget(widget)
 
        
 

 
    
main()