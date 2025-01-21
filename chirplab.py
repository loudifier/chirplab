import CLProject as clp
from qtpy.QtWidgets import QApplication
import sys
import os
import requests
import tempfile
from zipfile import ZipFile
import CLMeasurements
from CLGui import MainWindow
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
    else:
        clp.gui_mode = True
    
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
    clp.measurements = []
    for measurement in clp.project['measurements']:
        Measurement = getattr(CLMeasurements, measurement['type']) # dynamically invoke measurement class from measurement type string
        clp.measurements.append(Measurement(measurement['name'], measurement['params']))
    
    # get stimulus and response signals
    generate_stimulus()
    read_response()
    
    
    # if running in command-line mode, process measurements and output measurement data
    if args.c:
        for measurement in clp.measurements:
            measurement.measure()
            save_csv(measurement)
        
        # exit before launching GUI
        sys.exit()
            
    
    
    
    # set up main application window
    app = QApplication([])
    screen_size = app.screens()[0].size()
    window = MainWindow()
    window.resize(int(screen_size.width()*0.75), int(screen_size.height()*0.75))
    window.show()
    
    # add measurement tabs to main window
    for measurement in clp.measurements:
        measurement.init_tab()
        measurement.format_graph()
        window.tabs.addTab(measurement.tab, measurement.name)
    
    # run initial measurements and plot results
    for measurement in clp.measurements:
        measurement.measure()
        measurement.plot()
    
    # start main application loop
    app.exec()
 
        
    
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