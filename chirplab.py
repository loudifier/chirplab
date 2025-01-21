import CLProject as clp
from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QSplitter, QTextEdit, QComboBox
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
import numpy as np
from scipy.io import wavfile
import matplotlib.pyplot as plt
import sys
import CLMeasurements
from CLGui import CLTab, ChirpTab, CLParameter
from CLAnalysis import generate_stimulus, read_response


def main():
    # first, check that sox is available on the system. Prompt the user to install it or add some sort of fetch/installation routine
    print('todo: check for sox')
    # if not clp.sox_available():
    #     # on linux/OSX print message about `at-get install sox`, etc.
    #     # on Windows fetch binaries from https://sourceforge.net/projects/sox/files/sox/14.4.2/sox-14.4.2-win32.zip/download and unzip to /bin/
    
    if len(sys.argv) < 2:
        # chirplab started without any arguments. Generate a default New Project and launch gui
        clp.new_project()
        
    else:
        # parse input arguments
        # first argument is chirplab project file
        # -b for batch mode (command-line) processing
        # etc
        pass
        
    # initialize measurements from project
    measurements = []
    for measurement in clp.project['measurements']:
        Measurement = getattr(CLMeasurements, measurement['type']) # dynamically invoke measurement class from measurement type string
        measurements.append(Measurement(measurement['name'], measurement['params']))
    
    # get stimulus and response signals
    generate_stimulus()
    read_response()
    
    
    app = QApplication([])
    screen_size = app.screens()[0].size()
    
    window = MainWindow(measurements)
    window.resize(int(screen_size.width()*0.75), int(screen_size.height()*0.75))
    window.show()
    
    app.exec()
    
    
    

class MainWindow(QMainWindow):
    def __init__(self, measurements):
        super().__init__()
        self.measurements = measurements
        self.setWindowTitle('Chirplab')
        
        # main GUI structure for navigating between chirp parameters/IO and measurements
        tabs = QTabWidget()
        
        # First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
        chirp_tab = ChirpTab()
        tabs.addTab(chirp_tab,'Chirp Stimulus/Response')

        # Additional tab for each measurement
        for measurement in measurements:
            measurement.init_tab()
            tabs.addTab(measurement.tab, measurement.name)
        
        
        
        layout = QGridLayout() # base layout. Only 0,0 used
        layout.addWidget(tabs, 0,0)
        widget = QWidget() # Layout can't be applied directly to QMainWindow, need a base QWidget
        widget.setLayout(layout)
        self.setCentralWidget(widget)
 
        
    
        

 
    
main()