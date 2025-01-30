import CLProject as clp
from qtpy.QtWidgets import QMainWindow, QTabWidget, QTabBar, QGridLayout, QWidget, QApplication, QFileDialog, QErrorMessage, QMessageBox
from qtpy.QtGui import QAction
from CLGui.ChirpTab import ChirpTab
from CLMeasurements import init_measurements
from CLAnalysis import generate_stimulus
from pathlib import Path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        screen_size = QApplication.instance().screens()[0].size()
        self.resize(int(screen_size.width()*0.75), int(screen_size.height()*0.75))
        
        # main GUI structure for navigating between chirp parameters/IO and measurements
        self.tabs = QTabWidget()
        self.tabs.setTabBar(LockableTabBar()) # allow the user to rearrange the measurement tab order, but not the chirp tab or add measurement tab
        
        def load_project():
            # fully load (or reload) the current clp.project
            generate_stimulus()
            init_measurements()
            self.init_tabs()
            self.chirp_tab.update_stimulus()
            self.last_saved_project = clp.project.copy()
            self.setWindowTitle('Chirplab - ' + Path(clp.project_file).name)
        load_project()
        
        layout = QGridLayout() # base layout. Only 0,0 used
        layout.addWidget(self.tabs, 0,0)
        widget = QWidget() # Layout can't be applied directly to QMainWindow, need a base QWidget
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        
        
        
        menubar = self.menuBar()
        # todo: add top level keyboard shortcuts - CTRL+S for save, F5 for analyze, etc
        
        file_menu = menubar.addMenu(' &File   ')
        
        new_project = QAction('&New Project', self)
        file_menu.addAction(new_project)
        def create_new_project(checked):
            # todo: look into spawning a totally separate process. os.fork() works for Linux, but equivalent behavior on Windows is apparently impossible or convoluted to accomplish
            if self.is_project_changed():
                saved = self.save_prompt()
                if saved==QMessageBox.Cancel:
                    return # don't create a new project if the user cancels the dialog
            clp.new_project()
            load_project()
        new_project.triggered.connect(create_new_project)
        
        open_project = QAction('&Open Project', self)
        file_menu.addAction(open_project)
        def open_project_file(checked):
            if self.is_project_changed():
                saved = self.save_prompt()
                if saved==QMessageBox.Cancel:
                    return # don't create a new project if the user cancels the dialog
            file_dialog = QFileDialog()
            file_dialog.setWindowTitle('Open Project File')
            file_dialog.setFileMode(QFileDialog.ExistingFile)
            file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
            file_dialog.setNameFilters(['Chirplab project files (*.clp)', 'All files (*)'])
            file_dialog.setDirectory(clp.working_directory)
            
            if file_dialog.exec():
                file_path = file_dialog.selectedFiles()[0]
                
                # todo: test file loading corner cases, wrap in try/except, etc.
                clp.load_project_file(file_path) # sets working directory
                load_project()
        open_project.triggered.connect(open_project_file)
        
        file_menu.addSeparator()
        
        save_project = QAction('&Save Project', self)
        file_menu.addAction(save_project)
        def save_project_file(checked):
            if Path(clp.project_file).name == 'New Project':
                save_project_as(True)
            else:
                clp.save_project_file(clp.project_file)
                self.last_saved_project = clp.project.copy()
        save_project.triggered.connect(save_project_file)
        
        save_as = QAction('Save Project &as...', self)
        file_menu.addAction(save_as)
        def save_project_as(checked):
            file_dialog = QFileDialog()
            file_dialog.setWindowTitle('Save Project File')
            file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
            file_dialog.setNameFilters(['Chirplab project files (*.clp)', 'All files (*)'])
            file_dialog.setDirectory(clp.working_directory)
            def filterSelected(filter_string):
                default_suffix = filter_string.split('(*')[1].split(')')[0].split(' ')[0].split(',')[0].split(';')[0] # try to get the first actual file type suffix from the type string
                file_dialog.setDefaultSuffix(default_suffix)
            file_dialog.filterSelected.connect(filterSelected)
            
            saved = file_dialog.exec()
            if saved:
                file_path = file_dialog.selectedFiles()[0]
                clp.working_directory = str(Path(file_path).parent)
                try:
                    clp.save_project_file(file_path)
                    clp.project_file = file_path
                    clp.working_directory = str(Path(file_path).parent)
                    self.setWindowTitle('Chirplab - ' + Path(clp.project_file).name)
                except PermissionError as ex:
                    if clp.gui_mode:
                        error_box = QErrorMessage()
                        error_box.showMessage('Error writing project file \n' + str(ex))
                        error_box.exec()
            return saved
        self.save_project_as = save_project_as
        save_as.triggered.connect(save_project_as)
            
        
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
        
        analyze = QAction('Analyze Input File', self)
        measurement_menu.addAction(analyze)
        analyze.triggered.connect(self.chirp_tab.analyze)
        
        # todo: implement auto analyze option
        #auto_analyze = QAction('Automatically analyze when a parameter is updated', self)
        #measurement_menu.addAction(auto_analyze)
        
        # todo: implement show/hide noise floor option
        #noise_floor = QAction('Show/&Hide Measurement Noise Floor', self)
        #measurement_menu.addAction(noise_floor)
        
        measurement_menu.addSeparator()
        
        save_data = QAction('&Save Measurement Data', self)
        measurement_menu.addAction(save_data)
        
        
        # todo: add help menu items (after creating things for help menu items to point to...)
        #help_menu = menubar.addMenu(' &Help    ')
        
        #docs_link = QAction('Chirplab &documentation', self)
        #help_menu.addAction(docs_link)
        
        #issues_link = QAction('&Report a bug or request a feature', self)
        #help_menu.addAction(issues_link)
        
        #about = QAction('About Chirplab', self)
        #help_menu.addAction(about)
        
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
        
    def is_project_changed(self):
        # checks the current clp.project against the most recent saved or loaded project
        return clp.project != self.last_saved_project
    
    def save_prompt(self):
        save_message = QMessageBox()
        save_message.setWindowTitle('Save Project File?')
        save_message.setText('The project has changed since it was last saved. Save the current project?')
        save_message.setStandardButtons(QMessageBox.Save | QMessageBox.No | QMessageBox.Cancel)
        button = save_message.exec()
        if button == QMessageBox.Save:
            if Path(clp.project_file).name == 'New Project': # if project wasn't loaded from a project file, prompt to save as
                if not self.save_project_as(True):
                    return # user canceled out of save as dialog
            else:
                clp.save_project_file(clp.project_file)
        return button
    
    def closeEvent(self, event):
        if self.is_project_changed():
            save = self.save_prompt()
            if save == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()
    
    # todo: add a mouse and/or key event listener to the main window to check after every action whether the project has been changed and an asterisk should be added to the title bar?
        
        
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
            # todo: rearrange measurement list in project dict when tabs are moved
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