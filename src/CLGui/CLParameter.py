import CLProject as clp
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QAbstractSpinBox, QPushButton, QFileDialog, QCheckBox
import numpy as np
from CLGui import undo_stack

# collection of combination classes for displaying and entering configuration parameters
# typically a label on the left, text box or similar element in the middle, and sometimes a unit label or dropdown on the right
class CLParameter(QWidget):
    # generic text box parameter value
    def __init__(self, label_text, parameter_value, unit=None):
        super().__init__()
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        
        self.label = QLabel(label_text)
        self.layout.addWidget(self.label)
        
        self.text_box = QLineEdit(str(parameter_value))
        self.value = str(parameter_value)
        self.last_value = self.value # keep track of last value, to revert back to in case new entry fails data validation
        self.layout.addWidget(self.text_box)
        def editingFinished():
            self.value = self.text_box.text()
            if self.update_callback is not None:
                self.update_callback(self.value)
            self.last_value = self.value # if callback is not defined or update completes, just update last_value. If there is an issue during callback, assume revert sets current value to last_value
        self.text_box.editingFinished.connect(editingFinished)
        
        # Only add a unit label if the unit is specified
        if not unit is None:
            # if single unit is provided add a label, if a list of units is specified add a dropdown for unit selection
            if isinstance(unit, str):
                self.unit = QLabel(unit)
                self.layout.addWidget(self.unit)
            else:
                self.units = QComboBox()
                self.units.addItems(unit)
                self.layout.addWidget(self.units)
                def indexChanged(index):
                    if self.units_update_callback is not None:
                        self.units_update_callback(index)
                self.units.currentIndexChanged.connect(indexChanged)
        
        # define external callback functions to handle parameter updates
        self.update_callback = None
        self.units_update_callback = None
    
    def set_value(self, new_value):
        self.text_box.setText(str(new_value))
        self.value = self.text_box.text()
        self.last_value = self.value
    
    def revert(self):
        self.set_value(self.last_value)
      
        
class CLParamNum(QWidget):
    # numeric parameter using a spinbox for input and automatic checking of min/max values
    def __init__(self, label_text, parameter_value, unit=None, min_val=float('-inf'), max_val=float('inf'), numtype='float'):
        super().__init__()
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        
        self.label = QLabel(label_text)
        self.layout.addWidget(self.label)
        
        if numtype=='float':
            self.value = float(parameter_value)
        else:
            self.value = int(parameter_value)
        self.last_value = self.value
        self.min = min_val
        self.max = max_val
        
        # could make CLParamNum a subclass of CLParameter, but hokey stuff happens when adding/removing widgets, duplicated code is minimal
        # replace generic text box with spinbox
        #self.text_box.setParent(None)
        
        # any single one of these lines (plus the layout.update() call below) removes the text box
        #self.layout.removeWidget(self.text_box)
        #self.text_box.deleteLater() # this leads to an error being thrown when entering text into the spinbox
        #self.text_box.close()
        
        # don't actually use Qt's validation. Basic min/max/int checking is easy and changing values/limits of Qt classes fires callbacks and leads to confusing state machine problems
        self.spin_box = QDoubleSpinBox()
        self.spin_box.setMinimum(float('-inf'))
        self.spin_box.setMaximum(float('inf'))
        self.spin_box.setKeyboardTracking(False) # keep callbacks from firing until you press enter or click an arrow
        self.set_numtype(numtype)
        #self.layout.insertWidget(1, self.spin_box) # works, but the spinbox doesn't fill the middle the way it would if the spinbox is added directly instead of inserted
        #self.layout.update()
        self.layout.addWidget(self.spin_box)
        self.spin_box.setValue(self.value) # value can only be changed after adding to layout
        def valueChanged(new_val): # can also catch textChanged. textChanged and valueChanged are both called everytime a character is typed, not just editing finished. Might be worth catching textChanged and only validate on editing finished 
            if self.numtype == 'int':
                new_val = int(round(new_val))
            #self.spin_box.setValue(self.value) # fires an extra callback, call self.set_value() instead
            self.set_value(min(max(new_val, self.min), self.max)) # update if rounded or changed to min/max
            if self.update_callback is not None:
                self.update_callback(self.value)
            undo_stack.push(self.undo_redo, self.last_value)
            self.last_value = self.value
        
        self.spin_box.valueChanged.connect(valueChanged)
        
        # Only add a unit label if the unit is specified
        if not unit is None:
            # if single unit is provided add a label, if a list of units is specified add a dropdown for unit selection
            if isinstance(unit, str):
                self.unit = QLabel(unit)
                self.layout.addWidget(self.unit)
            else:
                self.units = QComboBox()
                self.units.addItems(unit)
                self.layout.addWidget(self.units)
                def unitsIndexChanged(index):
                    if not self.units_update_callback is None:
                        self.units_update_callback(index)
                self.units.currentIndexChanged.connect(unitsIndexChanged)
        
        # define external callback functions to handle parameter updates
        self.update_callback = None
        self.units_update_callback = None
        
    def set_min(self, new_min):
        self.min = new_min
        
    def set_max(self, new_max):
        self.max = new_max
        
    def set_value(self, new_value):
        self.value = new_value
        # supress valueChanged signal when programmatically setting the value
        self.spin_box.blockSignals(True)
        self.spin_box.setValue(self.value)
        self.spin_box.blockSignals(False)
        #self.last_value = new_value # don't update last_value here, so it can be recalled by update callback if needed
        
    def revert(self):
        self.set_value(self.last_value)
        self.value = self.last_value
        
    def set_numtype(self, new_type):
        # check for valid values, either 'float' or 'int'
        self.numtype = new_type
        if self.numtype == 'float':
            self.spin_box.setDecimals(2)
            self.spin_box.setStepType(QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
        else: # int
            self.spin_box.setStepType(QAbstractSpinBox.StepType.DefaultStepType)
            self.spin_box.setDecimals(0)
            # default step value should still be 1

    def undo_redo(self, undo_redo, value):
        self.set_value(value)
        self.last_value = value
        if self.update_callback is not None:
                self.update_callback(self.value)


class CLParamDropdown(QWidget):
    def __init__(self, label_text, item_list, unit=None, editable=False):
        super().__init__()
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        
        self.label = QLabel(label_text)
        self.layout.addWidget(self.label)
        
        self.dropdown = QComboBox()
        self.dropdown.addItems(item_list)
        self.layout.addWidget(self.dropdown)

        self.value = self.dropdown.currentText()
        self.last_index = 0
        def indexChanged(index):
            self.value = self.dropdown.currentText()
            if not self.update_callback is None:
                self.update_callback(index)
            self.last_value = self.value
            self.last_index = self.dropdown.currentIndex()
        self.dropdown.currentIndexChanged.connect(indexChanged)

        self.editable = editable
        if self.editable:
            self.dropdown.setEditable(True)
            self.dropdown.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            self.last_value = self.value

            def editingFinished():
                # just clicking the dropdown fires editingFinished(). Ignore if value isn't actually changed to avoid firing multiple times
                if self.dropdown.currentText() == self.last_value:
                    return
                indexChanged(-1) # follow the regular update callback with index of -1 to indicate text was edited instead of selecting a dropdown entry
            self.dropdown.lineEdit().editingFinished.connect(editingFinished)

            def set_value(new_value):
                self.dropdown.setCurrentText(str(new_value))
                self.value = self.dropdown.currentText()
                self.last_value = self.value
            self.set_value = set_value
        
        # Only add a unit label if the unit is specified
        if not unit is None:
            # if single unit is provided add a label, if a list of units is specified add a dropdown for unit selection
            if isinstance(unit, str):
                self.unit = QLabel(unit)
                self.layout.addWidget(self.unit)
            else:
                self.units = QComboBox()
                self.units.addItems(unit)
                self.layout.addWidget(self.units)
                def unitIndexChanged(index):
                    if not self.units_update_callback is None:
                        self.units_update_callback(index)
                self.units.currentIndexChanged.connect(unitIndexChanged)
        
        # define external callback functions to handle parameter updates
        self.update_callback = None
        self.units_update_callback = None

    def revert(self):
        self.dropdown.blockSignals(True)
        self.dropdown.setCurrentIndex(self.last_index)
        if self.editable:
            self.set_value(self.last_value)
        self.dropdown.blockSignals(False)


class CLParamFile(QWidget):
    # text box with button, with default behavior as a browse button to store a file path in the text box
    def __init__(self, label_text, parameter_value):
        super().__init__()
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        
        self.label = QLabel(label_text)
        self.layout.addWidget(self.label)
        
        self.text_box = QLineEdit(str(parameter_value))
        self.value = str(parameter_value)
        self.last_value = self.value # keep track of last value, to revert back to in case new entry fails data validation
        self.layout.addWidget(self.text_box)
        def editingFinished():
            self.value = self.text_box.text()
            if self.update_callback is not None:
                self.update_callback(self.value)
            self.last_value = self.value # if callback is not defined or update completes, just update last_value. If there is an issue during callback, assume revert sets current value to last_value
        self.text_box.editingFinished.connect(editingFinished)
        
        self.button = QPushButton('Browse...')
        self.layout.addWidget(self.button)
        self.starting_dir = '.'
        self.mime_types = None # set to a list of MIME types to add dropdowns for file type selection to browse dialog (e.g. ['audio/wav', 'application/octet-stream'])
        self.file_types = None # list of file type descriptions (e.g. ['WAV files (*.wav)', 'All files (*)']) Overrides MIME types
        self.browse_mode = 'open'
        def buttonClicked():
            if self.button_callback is None:
                self.browse() # browse by default, unless manually overridden
        self.button.clicked.connect(buttonClicked)
        
        # define external callback functions to handle parameter updates
        self.update_callback = None
        self.button_callback = None
        
    
    def set_value(self, new_value):
        self.value = str(new_value)
        self.text_box.setText(self.value)
    
    def revert(self):
        self.set_value(self.last_value)
        self.value = self.last_value
    
    def browse(self, starting_dir=None, file_types=None, browse_mode=None):
        if starting_dir is None:
            starting_dir = self.starting_dir
        if file_types is None:
            file_types = self.file_types
        if browse_mode is None:
            browse_mode = self.browse_mode
        
        file_dialog = QFileDialog()
        if browse_mode == 'save':
            file_dialog.setWindowTitle('Save File')
            file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        else:
            file_dialog.setWindowTitle('Open File')
            file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        
        if self.mime_types is not None:
            file_dialog.setMimeTypeFilters(self.mime_types)
        if self.file_types is not None:
            file_dialog.setNameFilters(self.file_types)
        def filterSelected(filter_string):
            default_suffix = filter_string.split('(*')[1].split(')')[0].split(' ')[0].split(',')[0].split(';')[0] # try to get the first actual file type suffix from the type string
            file_dialog.setDefaultSuffix(default_suffix)
        file_dialog.filterSelected.connect(filterSelected)
        
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            self.set_value(file_path)
            self.text_box.editingFinished.emit()
            

# collection of UI elements for configuring and generating a list of frequency points
# GUI wrapper for CLAnalysis.freq_points() to be used in output params section of measurement tabs
class FreqPointsParams(QWidget):
    def __init__(self, params=None):
        super().__init__()
        
        if params is None:
            params = {'min_freq':20, 'max_freq':20000, 'num_points':100, 'spacing':'log'}
        
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        self.layout.addWidget(QLabel('Frequency points'))
        
        self.min = CLParamNum('Min', params['min_freq'], 'Hz', 0.01, params['max_freq'])
        def update_min_freq(new_value):
            params['min_freq'] = new_value
            self.max.min = params['min_freq']
            if self.max.value < params['min_freq']: # shouldn't be possible, except maybe in the case of bugs or poorly constructed project files
                params['max_freq'] = params['min_freq'] # manually handle updates to avoid triggering multiple recalculations
                self.max.set_value(params['min_freq'])
            if self.update_callback is not None:
                self.update_callback()
        self.min.update_callback = update_min_freq
        self.min_auto = QCheckBox('auto')
        def update_min_auto(checked):
            params['min_auto'] = bool(checked)
            self.min.spin_box.setEnabled(not bool(checked))
            if self.calc_min_auto is not None:
                new_min = self.calc_min_auto() # get automatic min freq from containing measurement
                self.min.spin_box.setValue(new_min) # set value in spin_box directly to trigger recalculation
        self.min_auto.stateChanged.connect(update_min_auto)
        self.calc_min_auto = None
        self.min_auto.setChecked(params['min_auto'])
        self.min.layout.addWidget(self.min_auto)
        self.layout.addWidget(self.min)
        
        self.max = CLParamNum('Max', params['max_freq'], 'Hz', params['min_freq'], clp.project['sample_rate']/2)
        def update_max_freq(new_value):
            params['max_freq'] = new_value
            self.min.max = params['max_freq']
            if self.min.value > params['max_freq']: # shouldn't be possible, except maybe in the case of bugs or poorly constructed project files
                params['min_freq'] = params['max_freq'] # manually handle updates to avoid triggering multiple recalculations
                self.min.set_value(params['max_freq'])
            if self.update_callback is not None:
                self.update_callback()
        self.max.update_callback = update_max_freq
        self.max_auto = QCheckBox('auto')
        def update_max_auto(checked):
            params['max_auto'] = bool(checked)
            self.max.spin_box.setEnabled(not bool(checked))
            if self.calc_max_auto is not None:
                new_max = self.calc_max_auto() # get automatic max freq from containing measurement
                self.max.spin_box.setValue(new_max) # set value in spin_box directly to trigger recalculation
        self.max_auto.stateChanged.connect(update_max_auto)
        self.calc_max_auto = None
        self.max_auto.setChecked(params['max_auto'])
        self.max.layout.addWidget(self.max_auto)
        self.layout.addWidget(self.max)
        
        self.spacing = CLParamDropdown('Spacing', ['log','linear','points per octave'])
        if params['spacing']=='linear':
            self.spacing.dropdown.setCurrentIndex(1)
        if params['spacing']=='octave':
            self.spacing.dropdown.setCurrentIndex(2)
        self.layout.addWidget(self.spacing)
        def update_spacing(index):
            # if switching from log or linear to points per octave, update num_points to get roughly the same resolution
            if index==2 and params['spacing'] != 'octave':
                num_octaves = np.log2(params['max_freq']/params['min_freq'])
                params['num_points'] = round(params['num_points'] / num_octaves)
                self.num_points.set_value(params['num_points'])
            
            # if switching from points per octave to log or linear, update num_points to get roughly the same resolution
            if index<2 and params['spacing'] == 'octave':
                num_octaves = np.log2(params['max_freq']/params['min_freq'])
                params['num_points'] = round(params['num_points'] * num_octaves)
                self.num_points.set_value(params['num_points'])
                    
            
            if index==0:
                params['spacing'] = 'log'
            if index==1:
                # todo: automatically switch graph to linear scaling
                # `self.tab.graph.setLogMode(False, False)` in callback in measurement doesn't seem to work
                params['spacing'] = 'linear'
            if index==2:
                params['spacing'] = 'octave'
            if self.update_callback is not None:
                self.update_callback()
        self.spacing.update_callback = update_spacing
        
        self.num_points = CLParamNum('Number of points', params['num_points'], None, 1, numtype='int')
        self.layout.addWidget(self.num_points)
        def update_num_points(new_value):
            params['num_points'] = new_value
            if self.update_callback is not None:
                self.update_callback()
        self.num_points.update_callback = update_num_points
        
        self.round_points = QCheckBox('Round points to nearest Hz')
        self.layout.addWidget(self.round_points)
        def update_round_points(checked):
            params['round_points'] = bool(checked)
            if self.update_callback is not None:
                self.update_callback()
        self.round_points.stateChanged.connect(update_round_points)
        
        
        def update_min_max():
            if params['min_auto'] and self.calc_min_auto is not None:
                params['min_freq'] = self.calc_min_auto()
                self.min.set_value(params['min_freq'])
            if params['max_auto'] and self.calc_max_auto is not None:
                params['max_freq'] = self.calc_max_auto()
                self.max.set_value(params['max_freq'])
        self.update_min_max = update_min_max
        
        
        self.update_callback = None
        
        

# not enough additional functionality to justify a CL combo class            
#class CLParamCheckbox(QWidget):
#    def __init__(self, label_text, checked=False, enabled=True):
#        super().__init__()

#        self.checkbox = QCheckBox(label_text)
        
        # update callback here
        
#        self.label = QLabel(label_text)
#        self.layout.addWidget(self.label)
        
#        self.update_callback = None