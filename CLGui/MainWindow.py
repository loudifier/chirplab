import CLProject as clp
from qtpy.QtWidgets import QMainWindow, QTabWidget, QTabBar, QGridLayout, QWidget, QApplication
from qtpy.QtGui import QAction
from CLGui.ChirpTab import ChirpTab
from CLAnalysis import generate_stimulus
from CLMeasurements import init_measurements

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        screen_size = QApplication.instance().screens()[0].size()
        self.resize(int(screen_size.width()*0.75), int(screen_size.height()*0.75))
        
        self.setWindowTitle('Chirplab')
        
        # main GUI structure for navigating between chirp parameters/IO and measurements
        self.tabs = QTabWidget()
        self.tabs.setTabBar(LockableTabBar()) # allow the user to rearrange the measurement tab order, but not the chirp tab or add measurement tab
        
        # build full set of chirp, measurement, and add measurement tabs from the current clp.project
        self.init_tabs()
        
        # run and plot initial measurements
        self.chirp_tab.analyze()
        
        layout = QGridLayout() # base layout. Only 0,0 used
        layout.addWidget(self.tabs, 0,0)
        widget = QWidget() # Layout can't be applied directly to QMainWindow, need a base QWidget
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        
        
        
        menubar = self.menuBar()
        
        
        file_menu = menubar.addMenu(' &File   ')
        
        new_project = QAction('&New Project', self)
        file_menu.addAction(new_project)
        def create_new_project(checked):
            # todo: look into spawning a totally separate process. os.fork() works for Linux, but equivalent behavior on Windows is apparently impossible or convoluted to accomplish
            # check if current project has unsaved changes
            clp.new_project()
            init_measurements()
            self.chirp_tab.update_stimulus()
            self.init_tabs()
        new_project.triggered.connect(create_new_project)
        
        open_project = QAction('&Open Project', self)
        file_menu.addAction(open_project)
        
        file_menu.addSeparator()
        
        save_project = QAction('&Save Project', self)
        file_menu.addAction(save_project)
        
        save_as = QAction('Save Project &as...', self)
        file_menu.addAction(save_as)
        
        file_menu.addSeparator()
        
        quit_action = QAction('&Quit', self)
        file_menu.addAction(quit_action)
        quit_action.triggered.connect(self.close)
        
        
        measurement_menu = menubar.addMenu(' &Measurement')
        
        add_measurement = QAction('&Add Measurement', self)
        measurement_menu.addAction(add_measurement)
        
        remove_measurement = QAction('&Remove Current Measurement', self)
        measurement_menu.addAction(remove_measurement)
        # add something in currentChanged slot to gray out if currently on chirp tab
        
        measurement_menu.addSeparator()
        
        analyze = QAction('Analyze Input File (F5)', self)
        measurement_menu.addAction(analyze)
        
        noise_floor = QAction('Show/&Hide Measurement Noise Floor', self)
        measurement_menu.addAction(noise_floor)
        
        measurement_menu.addSeparator()
        
        save_data = QAction('&Save Measurement Data', self)
        measurement_menu.addAction(save_data)
        
        
        
    def init_tabs(self):
        # build (or rebuild) full set of chirp, measurement, and add measurement tabs from the current clp.project
        self.tabs.clear()
        
        # First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
        self.chirp_tab = ChirpTab()
        self.tabs.addTab(self.chirp_tab,'Chirp Stimulus/Response')
        
        # add measurement tabs to main window
        for measurement in clp.measurements:
            measurement.init_tab()
            measurement.format_graph()
            self.tabs.addTab(measurement.tab, measurement.name)
        
        # last tab - add measurement button (individual measurement tabs to be inserted at index -2)
        self.tabs.addTab(QWidget(), ' + ')
        
        # run initial measurements and plot results
        #for measurement in clp.measurements:
        #    measurement.measure()
        #    measurement.plot()
        
class LockableTabBar(QTabBar):
    def __init__(self):
        super().__init__()
    
        # allow user to rearrange measurement tabs (but not chirp tab or add measurement tab)
        def tab_clicked(index):
            if index in self.locked_tabs():
                self.setMovable(False)
            else:
                self.setMovable(True)
        self.tabBarClicked.connect(tab_clicked)
        
        self.tab_was_moved = False
        self.tab_moved_from = 0
        self.tab_moved_to = 0
        def tab_moved(to_index, from_index): # the documentation for the tabMoved signal has from/to backwards
            self.tab_was_moved = True # set flag for mouseReleaseEvent handler to check if the move was valid
            self.tab_moved_from = from_index # keep track of which tab was actually moved
            self.tab_moved_to = to_index
        self.tabMoved.connect(tab_moved)
    
    def locked_tabs(self):
        # lock the chirp tab and add measurement tab
        return [0, self.count()-1]
    
    # override mouseReleaseEvent to catch if the user tries to drag the chirp tab or add measurement tab
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.tab_was_moved:
            self.tab_was_moved = False # reset was_moved flag regardless of whether the move was valid

            if self.tab_moved_to in self.locked_tabs(): # a measurement tab was moved to the beginning or the end of the tab bar - revert the move
                #self.moveTab(self.tab_moved_to, self.tab_moved_from) # only moves the tab button, but doesn't change the tab content
                self.parent().insertTab(self.tab_moved_from, self.parent().widget(self.tab_moved_to), self.tabText(self.tab_moved_to)) # actually moves the full tab
                self.setCurrentIndex(self.tab_moved_from)