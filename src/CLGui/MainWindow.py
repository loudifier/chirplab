import CLProject as clp
from qtpy.QtWidgets import QMainWindow, QTabWidget, QTabBar, QGridLayout, QWidget, QApplication, QFileDialog, QErrorMessage, QMessageBox, QDialog, QDialogButtonBox, QVBoxLayout
from qtpy.QtGui import QAction, QIcon
from CLGui import ChirpTab, CLParamDropdown, CLParameter
from CLMeasurements import init_measurements, is_valid_measurement_name
from CLAnalysis import generate_stimulus, save_csv
from pathlib import Path
import CLMeasurements
from copy import deepcopy
import pyqtgraph as pg
import pyqtgraph.exporters # just calling pg.exporters... doesn't work unless pyqtgraph.exporters is manually imported
import yaml

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(str(Path(__file__).parent) + '/icon.png'))

        screen_size = QApplication.instance().screens()[0].size()
        self.resize(int(screen_size.width()*0.75), int(screen_size.height()*0.75))
        
        # main GUI structure for navigating between chirp parameters/IO and measurements
        self.tabs = QTabWidget()
        self.tabs.setTabBar(LockableTabBar()) # allow the user to rearrange the measurement tab order, but not the chirp tab or add measurement tab
        
        # allow adding a measurement by clicking on the last tab in the tab bar
        def tab_changed(index):
            if self.tabs.last_tab_clicked != self.tabs.count()-1: # user didn't actually click on add measurement tab, they dragged another measurement all the way over to the right
                return
            if index == self.tabs.count()-1: # user clicked add measurement tab
                self.tabs.setCurrentIndex(self.tabs.prev_tab) # change back to tab that was showing before the click
                add_measurement_dialog()
        self.tabs.currentChanged.connect(tab_changed)
        self.tabs.last_tab_clicked = 0
        self.tabs.prev_tab = 0
        def tabs_clicked(index):
            self.tabs.prev_tab = self.tabs.currentIndex()
            self.tabs.last_tab_clicked = index
            if not index: # chirp tab
                remove_measurement.setEnabled(False)
            elif index < self.tabs.count()-1: # measurement tab
                remove_measurement.setEnabled(True)
            # don't check for add measurement tab, handle in tab_changed
        self.tabs.tabBarClicked.connect(tabs_clicked)
        
        
        def load_project():
            # fully load (or reload) the current clp.project
            generate_stimulus()
            init_measurements()
            self.init_tabs()
            self.chirp_tab.update_stimulus()
            self.last_saved_project = deepcopy(clp.project)
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
            self.chirp_tab.io_changed.connect(update_analyze_text)
            update_analyze_text()
            self.chirp_tab.capture_finished.connect(enable_capture)
            self.chirp_tab.play_finished.connect(enable_play)
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
                self.chirp_tab.io_changed.connect(update_analyze_text)
                update_analyze_text()
                self.chirp_tab.capture_finished.connect(enable_capture)
                self.chirp_tab.play_finished.connect(enable_play)
        open_project.triggered.connect(open_project_file)
        
        file_menu.addSeparator()
        
        save_project = QAction('&Save Project', self)
        file_menu.addAction(save_project)
        def save_project_file(checked):
            if Path(clp.project_file).name == 'New Project':
                save_project_as(True)
            else:
                clp.save_project_file(clp.project_file)
                self.last_saved_project = deepcopy(clp.project)
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
                    self.last_saved_project = deepcopy(clp.project)
                except PermissionError as ex:
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
        def add_measurement_dialog():
            if AddMeasurementDialog(self).exec():
                remove_measurement.setEnabled(True) # if measurement is added its tab will be activated
        add_measurement.triggered.connect(add_measurement_dialog)
        def add_new_measurement(measurement_type, name, params=None):
            type_index = CLMeasurements.MEASUREMENT_TYPES.index(measurement_type)
            clp.measurements.append(getattr(CLMeasurements, CLMeasurements.MEASUREMENT_TYPES[type_index])(name, params))
            clp.project['measurements'].append(clp.measurements[-1].params)
            clp.measurements[-1].init_tab() 
            clp.measurements[-1].format_graph()
            clp.measurements[-1].measure()
            clp.measurements[-1].plot()
            self.tabs.insertTab(self.tabs.count()-1, clp.measurements[-1].tab, name)
            self.tabs.setCurrentIndex(self.tabs.count()-2)
            clp.measurements[-1].param_section.expand() # todo: figure out why measurement params sections do not actually expand in .init_tab(). Works fine for some measurements but not others, and there are only problems when adding a new measurment to the current project, not when opening/initializing a project.
        self.add_new_measurement = add_new_measurement
        
        remove_measurement = QAction('&Remove Current Measurement', self)
        remove_measurement.setEnabled(False)
        measurement_menu.addAction(remove_measurement)
        def remove_measurement_prompt(checked=True):
            remove_message = QMessageBox()
            remove_message.setWindowTitle('Remove Measurement?')
            remove_message.setText("Are you sure you want to remove the '" + clp.measurements[self.tabs.currentIndex()-1].params['name'] + "' measurement?")
            remove_message.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            button = remove_message.exec()
            if button == QMessageBox.Yes:
                if button:
                    tab_index = self.tabs.currentIndex()
                    self.tabs.blockSignals(True) # removing a tab activates the tab to the right. Keep add measurement dialog from firing
                    self.tabs.removeTab(self.tabs.currentIndex())
                    self.tabs.setCurrentIndex(tab_index-1)
                    self.tabs.blockSignals(False)
                    if not self.tabs.currentIndex(): # ended up back on the chirp tab
                        remove_measurement.setEnabled(False)
                    clp.measurements.pop(tab_index-1)
                    clp.project['measurements'].pop(tab_index-1)
            return button
        remove_measurement.triggered.connect(remove_measurement_prompt)
        
        measurement_menu.addSeparator()

        load_preset = QAction('Add Measurement From Preset', self)
        measurement_menu.addAction(load_preset)
        def load_measurement_preset(checked):
            file_dialog = QFileDialog()
            file_dialog.setWindowTitle('Load Measurement Preset')
            file_dialog.setFileMode(QFileDialog.ExistingFile)
            file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
            file_dialog.setNameFilters(['Chirplab measurement preset (*.clm)', 'All files (*)'])
            file_dialog.setDirectory(clp.working_directory)
            
            if file_dialog.exec():
                file_path = file_dialog.selectedFiles()[0]
                with open(file_path) as in_file:
                    params = yaml.safe_load(in_file)
                    params.pop('chirplab_version')
                    self.add_new_measurement(params['type'], params['name'], params)
        load_preset.triggered.connect(load_measurement_preset)

        save_preset = QAction('Save Measurement Preset', self)
        measurement_menu.addAction(save_preset)
        def save_measurement_preset(checked):
            tab_index = self.tabs.currentIndex()
            file_dialog = QFileDialog()
            file_dialog.setWindowTitle('Save Measurement Preset')
            file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
            file_dialog.selectFile(clp.measurements[tab_index-1].params['name'] + '.clm')
            file_dialog.setNameFilters(['Chirplab measurement preset (*.clm)',  'All files (*)'])
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
                    with open(file_path, 'w') as out_file:
                        params = deepcopy(clp.measurements[tab_index-1].params)
                        params['chirplab_version'] = clp.CHIRPLAB_VERSION # insert chirplab version to allow handling breaking changes between versions
                        out_file.write(yaml.dump(params))
                except PermissionError as ex:
                    error_box = QErrorMessage()
                    error_box.showMessage('Error writing measurement data \n' + str(ex))
                    error_box.exec()
            return saved
        save_preset.triggered.connect(save_measurement_preset)

        measurement_menu.addSeparator()
        
        analyze = QAction('Analyze Input File', self)
        measurement_menu.addAction(analyze)
        def analyze_or_capture():
            if clp.project['input']['mode'] == 'file':
                self.chirp_tab.input_params.file_input.analyze()
            else:
                self.chirp_tab.input_params.device_input.capture()
                analyze.setEnabled(False)
                if clp.project['output']['mode'] == 'device':
                    generate.setEnabled(False)
        analyze.triggered.connect(analyze_or_capture)
        def update_analyze_text():
            if clp.project['input']['mode'] == 'file':
                analyze.setText('Analyze Input File')
            else: # input is in device mode
                if clp.project['output']['mode'] == 'file':
                    analyze.setText('Capture Response')
                else:
                    analyze.setText('Play and Capture')
        update_analyze_text()
        self.chirp_tab.io_changed.connect(update_analyze_text)
        def enable_capture():
            analyze.setEnabled(True)
        self.chirp_tab.capture_finished.connect(enable_capture)

        generate = QAction('Generate Stimulus File')
        measurement_menu.addAction(generate)
        def generate_or_play():
            if clp.project['output']['mode'] == 'file':
                self.chirp_tab.output_params.file_output.generate_output_file()
            else:
                self.chirp_tab.output_params.device_output.play_stimulus()
                generate.setEnabled(False)
        generate.triggered.connect(generate_or_play)
        def update_generate_text():
            if clp.project['output']['mode'] == 'file':
                generate.setText('Generate Stimulus File')
            else:
                generate.setText('Play Stimulus')
        update_generate_text()
        self.chirp_tab.io_changed.connect(update_generate_text)
        def enable_play():
            generate.setEnabled(True)
        self.chirp_tab.play_finished.connect(enable_play)
        
        # todo: implement auto analyze option
        #auto_analyze = QAction('Automatically analyze when a parameter is updated', self)
        #measurement_menu.addAction(auto_analyze)
        
        # todo: implement show/hide noise floor option
        #noise_floor = QAction('Show/&Hide Measurement Noise Floor', self)
        #measurement_menu.addAction(noise_floor)
        
        measurement_menu.addSeparator()
        
        save_data = QAction('&Save Measurement/Graph Data', self)
        measurement_menu.addAction(save_data)
        def save_measurement_data(checked=True):
            tab_index = self.tabs.currentIndex()
            file_dialog = QFileDialog()
            file_dialog.setWindowTitle('Save Measurement Data')
            file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
            if tab_index:
                file_dialog.selectFile(clp.measurements[tab_index-1].params['name'] + '.csv')
                file_dialog.setNameFilters(['Output points (*.csv)', 'Graph image (*.png)',  'All files (*)'])
            else: # only save graph image from chirp tab
                file_dialog.selectFile('chirp stimulus-response.png')
                file_dialog.setNameFilters(['Graph image (*.png)',  'All files (*)'])
            file_dialog.setDirectory(clp.working_directory)
            def filterSelected(filter_string):
                default_suffix = filter_string.split('(*')[1].split(')')[0].split(' ')[0].split(',')[0].split(';')[0] # try to get the first actual file type suffix from the type string
                file_dialog.setDefaultSuffix(default_suffix)
            file_dialog.filterSelected.connect(filterSelected)
            
            saved = file_dialog.exec()
            if saved:
                file_path = file_dialog.selectedFiles()[0]
                clp.working_directory = str(Path(file_path).parent)
                
                file_type = Path(file_path).suffix
                if file_type.casefold() == '.png'.casefold(): # save graph image with default pyqtgraph settings
                    if tab_index: # export measurement graph
                        exporter = pg.exporters.ImageExporter(clp.measurements[self.tabs.currentIndex()-1].tab.graph.plotItem)
                    else: # export chirp tab graph
                        exporter = pg.exporters.ImageExporter(self.chirp_tab.graph.plotItem)
                    exporter.export(file_path)
                else: # for any other extension default to exporting as .csv
                    if tab_index: # export measurement data
                        try:
                            save_csv(clp.measurements[self.tabs.currentIndex()-1], file_path)
                        except PermissionError as ex:
                            error_box = QErrorMessage()
                            error_box.showMessage('Error writing measurement data \n' + str(ex))
                            error_box.exec()
                    else:
                        pass # silently fail if trying to save chirp tab as anything other than .png. Throw a message of some sort?
            return saved
        save_data.triggered.connect(save_measurement_data)
        
        
        # todo: add help menu items (after creating things for help menu items to point to...)
        #help_menu = menubar.addMenu(' &Help    ')
        
        #docs_link = QAction('Chirplab &documentation', self)
        #help_menu.addAction(docs_link)
        
        #issues_link = QAction('&Report a bug or request a feature', self)
        #help_menu.addAction(issues_link)
        
        #about = QAction('About Chirplab', self)
        #help_menu.addAction(about)
        
    def init_tabs(self):
        self.tabs.blockSignals(True)
        
        # build (or rebuild) full set of chirp, measurement, and add measurement tabs from the current clp.project
        self.tabs.clear()
        
        # First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
        self.chirp_tab = ChirpTab()
        self.tabs.addTab(self.chirp_tab,'Chirp Stimulus/Response')
        
        # add measurement tabs to main window
        for measurement in clp.measurements:
            measurement.init_tab()
            measurement.format_graph()
            self.tabs.addTab(measurement.tab, measurement.params['name'])
        
        # last tab - add measurement button (individual measurement tabs to be inserted at index -2)
        self.tabs.addTab(QWidget(), ' + ')
        
        self.tabs.blockSignals(False)
        
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
            
            if to_index not in self.locked_tabs(): # if move is valid, reorder list of measurements
                clp.project['measurements'].insert(to_index-1, clp.project['measurements'].pop(from_index-1)) # reorder project parameters so they can be saved/loaded in the correct order
                clp.measurements.insert(to_index-1, clp.measurements.pop(from_index-1)) # reorder actual measurement objects for cases where they are referenced by index
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
                
class AddMeasurementDialog(QDialog):
    def __init__(self, main_window):
        super().__init__()
        
        self.setWindowTitle('Add new measurement')
        
        # todo: figure out how to not have a window icon

        layout = QVBoxLayout()
        
        measurement_type_names = []
        for measurement_type in CLMeasurements.MEASUREMENT_TYPES:
            measurement_type_names.append(getattr(CLMeasurements, measurement_type).measurement_type_name)
        
        type_dropdown = CLParamDropdown('Measurement type', measurement_type_names)
        layout.addWidget(type_dropdown)
        def update_type(index):
            if measurement_name.value.strip() in measurement_type_names:
                measurement_name.set_value(measurement_type_names[index])
                measurement_name.last_value = measurement_type_names[index]
        type_dropdown.update_callback = update_type
        
        measurement_name = CLParameter('New measurement name', measurement_type_names[0])
        layout.addWidget(measurement_name)
        def update_name(new_name):
            new_name = new_name.strip()
            if not is_valid_measurement_name(new_name):
                measurement_name.set_value(measurement_name.last_value)
                return
            measurement_name.set_value(new_name) # in case whitespace was removed
            measurement_name.last_value = new_name
        measurement_name.update_callback = update_name
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)
        def add_new_measurement():
            measurement_type = CLMeasurements.MEASUREMENT_TYPES[type_dropdown.dropdown.currentIndex()]
            main_window.add_new_measurement(measurement_type, measurement_name.value)
            self.accept()
        button_box.accepted.connect(add_new_measurement)
        button_box.rejected.connect(self.reject)
        
        self.setLayout(layout)
        
        