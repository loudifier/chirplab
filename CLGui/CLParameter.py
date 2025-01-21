from qtpy.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QAbstractSpinBox

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
            if not self.update_callback is None:
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
                    if not self.units_update_callback is None:
                        self.units_update_callback(index)
                self.units.currentIndexChanged.connect(indexChanged)
        
        # define external callback functions to handle parameter updates
        self.update_callback = None
        self.units_update_callback = None
    
    def set_value(self, new_value):
        self.text_box.setText(new_value)
    
    def revert(self):
        self.set_value(self.last_value)
        self.value = self.last_value
      
        
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
        self.set_numtype(numtype)
        #self.layout.insertWidget(1, self.spin_box) # works, but the spinbox doesn't fill the middle the way it would if the spinbox is added directly instead of inserted
        #self.layout.update()
        self.layout.addWidget(self.spin_box)
        self.spin_box.setValue(self.value) # value can only be changed after adding to layout
        def valueChanged(new_val): # can also catch textChanged. textChanged and valueChanged are both called everytime a character is typed, not just editing finished. Might be worth catching textChanged and only validate on editing finished
            if self.numtype == 'int':
                new_val = int(round(new_val))
            self.value = min(max(new_val, self.min), self.max)
            self.spin_box.setValue(self.value) # update if rounded or changed to min/max. Does this fire extra callbacks?
            if not self.update_callback is None:
                self.update_callback(self.value)
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
        self.spin_box.setValue(new_value)
        
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


class CLParamDropdown(QWidget):
    def __init__(self, label_text, item_list, unit=None):
        super().__init__()
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        
        self.label = QLabel(label_text)
        self.layout.addWidget(self.label)
        
        self.dropdown = QComboBox()
        self.dropdown.addItems(item_list)
        self.layout.addWidget(self.dropdown)
        
        def indexChanged(index):
            if not self.update_callback is None:
                self.update_callback(index)
        self.dropdown.currentIndexChanged.connect(indexChanged)
        
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

# not enough additional functionality to justify a CL combo class            
#class CLParamCheckbox(QWidget):
#    def __init__(self, label_text, checked=False, enabled=True):
#        super().__init__()

#        self.checkbox = QCheckBox(label_text)
        
        # update callback here
        
#        self.label = QLabel(label_text)
#        self.layout.addWidget(self.label)
        
#        self.update_callback = None