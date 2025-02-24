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

        if clp.IS_BUNDLED and sys.platform == 'win32': # hide console window when bundled, in GUI mode, on Windows 11, when started by double-clicking
            # todo: see if there is a way to keep the console window from flashing up (and/or see if https://github.com/pyinstaller/pyinstaller/issues/8022 has been resolved)
            import ctypes
            import win32gui
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            process_array = (ctypes.c_uint8 * 1)()
            num_processes = kernel32.GetConsoleProcessList(process_array, 1)
            if num_processes == 1: # parent proccess count *should* be 1 if double-clicked. This may not cover some corner cases, but the worst that would happen is the console is hidden when calling from console or the console is left open when double-clicking the GUI
                # for some reason you need to set the console window to the foreground and then retrieve it, or else ShowWindow minimizes the window instead of hiding it
                hWnd = kernel32.GetConsoleWindow()
                win32gui.SetForegroundWindow(hWnd)
                hWnd = win32gui.GetForegroundWindow()
                win32gui.ShowWindow(hWnd, 0) # hide the console window
        
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