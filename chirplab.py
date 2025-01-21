# %%
import CLProject as clp

from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QSplitter, QTextEdit, QComboBox
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
import numpy as np
from scipy.io import wavfile
import matplotlib.pyplot as plt
import sys
import os
import requests
import tempfile
from zipfile import ZipFile
import subprocess
import CLMeasurements
from CLGui import CLTab, ChirpTab, CLParameter
from CLAnalysis import generate_stimulus, read_response, save_csv
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', nargs='?', help='path to ChirpLab project file to open or process (required for command-line mode)')
    parser.add_argument('-c', action='store_true', help='process input project file and output data in command-line mode')
    args = parser.parse_args()

    if args.c:
        if not args.project:
            print('please specify ChirpLab project file for command-line processing')
            sys.exit()
        
        #load project file
            #error message if there is a problem loading project file, exit
        clp.new_project()
    
    if args.project:
        print('load project')
        # pop up error message box if there is a problem loading project file, options to create new project or quit
        clp.new_project()
    else:
        # chirplab started without any arguments. Generate a default New Project and launch gui
        clp.new_project()
    
    
    # first, check that sox is available on the system. Download if it isn't
    check_sox()    
    
    # initialize measurements from project
    measurements = []
    for measurement in clp.project['measurements']:
        Measurement = getattr(CLMeasurements, measurement['type']) # dynamically invoke measurement class from measurement type string
        measurements.append(Measurement(measurement['name'], measurement['params']))
    
    # get stimulus and response signals
    generate_stimulus()
    read_response()
    
    
    # if running in command-line mode, process measurements and output measurement data
    if args.c:
        for measurement in measurements:
            measurement.measure()
            save_csv(measurement)
        
        # exit before launching GUI
        sys.exit()
            
    
    
    
    # set up main application window
    app = QApplication([])
    screen_size = app.screens()[0].size()
    window = MainWindow(measurements)
    window.resize(int(screen_size.width()*0.75), int(screen_size.height()*0.75))
    window.show()
    
    # add measurement tabs to main window
    for measurement in measurements:
        measurement.init_tab()
        window.tabs.addTab(measurement.tab, measurement.name)
    
    # run initial measurements and plot results
    for measurement in measurements:
        measurement.measure()
        measurement.plot()
    
    # start main application loop
    app.exec()
    
    
    

class MainWindow(QMainWindow):
    def __init__(self, measurements):
        super().__init__()
        self.measurements = measurements
        self.setWindowTitle('Chirplab')
        
        # main GUI structure for navigating between chirp parameters/IO and measurements
        self.tabs = QTabWidget()
        
        # First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
        chirp_tab = ChirpTab()
        self.tabs.addTab(chirp_tab,'Chirp Stimulus/Response')
        
        layout = QGridLayout() # base layout. Only 0,0 used
        layout.addWidget(self.tabs, 0,0)
        widget = QWidget() # Layout can't be applied directly to QMainWindow, need a base QWidget
        widget.setLayout(layout)
        self.setCentralWidget(widget)
 
        
    
def check_sox():
    # assuming Windows for now (prompt user to `apt-get install sox` on linux), probably needs to be handled differently in compiled .exe
    if not os.path.exists(clp.sox_path): # pretty unlikely user will already have sox available on PATH, easier to download and use portable version in chirplab folder
        try:
            print('SoX not found, downloading from ' + clp.sox_dl_url + '...')
            with tempfile.TemporaryFile() as sox_temp:
                content = requests.get(clp.sox_dl_url, stream=True).content
                sox_temp.write(content)
                sox_zip = ZipFile(sox_temp, 'r')
                sox_zip.extractall(clp.bin_dir) # creates target folder and/or merges zip contents with target folder contents, no need to check for/create bin folder
                # add something to test that sox is working correctly?
                #     Sox executable works fine for non-audio commands (--version, etc) even without any of its DLLs
                #     Sox outputs to console weirdly, so capturing and parsing output is annoying
        except:
            print('error while downloading SoX')
            sys.exit()
       
    
    
 
    
main()