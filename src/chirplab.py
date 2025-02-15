import CLProject as clp
from pyqtgraph.Qt import mkQApp
from qtpy.QtCore import Qt
import sys
from pathlib import Path 
from CLGui import MainWindow
from CLAnalysis import check_sox, generate_stimulus, read_response, save_csv, FormatNotSupportedError
import argparse
import numpy as np
from CLMeasurements import init_measurements


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', nargs='?', help='path to ChirpLab project file to open or process (required for command-line mode)')
    parser.add_argument('-c', action='store_true', help='process input project file and output data in command-line mode')
    args = parser.parse_args()

    if args.c:
        if not args.project:
            print('please specify ChirpLab project file for command-line processing')
            sys.exit(1)
    else:
        clp.gui_mode = True
        # initialize main application
        app = mkQApp() # same as a regular QApplication, but first sets up some environment stuff to handle DPI scaling across multiple monitors
        app.setAttribute(Qt.ApplicationAttribute.AA_DisableWindowContextHelpButton)
    
    if args.project:
        try:
            clp.load_project_file(args.project)
        except FileNotFoundError as e:
            print(e)
            if args.c:
                sys.exit(1)
            print('creating a new project...')
            clp.new_project()
    else:
        # chirplab started without any arguments. Generate a default New Project and launch gui
        clp.new_project()
    
    
    # check that sox is available on the system. Download if it isn't
    check_sox()
    
    # if running in command-line mode, process measurements and output measurement data
    if not clp.gui_mode:
        
        # initialize measurements from project
        init_measurements()
        
        # get stimulus and response signals
        generate_stimulus()
        try:
            read_response()
        except (FileNotFoundError, FormatNotSupportedError) as e:
            print(e)
            if not clp.gui_mode:
                sys.exit(1)
            else:
                clp.signals['response'] = np.zeros(len(clp.signals['stimulus']))
                clp.signals['noise'] = []
        for measurement in clp.measurements:
            measurement.measure()
            save_csv(measurement, '', Path(args.project).parent)
            # todo: throw a warning that some output files will be overwritten if multiple measurements have the same name
        
        # exit before launching GUI
        sys.exit()
            
    
    # not CLI mode, launch GUI
    window = MainWindow()
    window.show()
    
    # start main application loop
    app.exec()
 
main()