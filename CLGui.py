import CLProject as clp
from qtpy.QtWidgets import QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSplitter, QLineEdit, QComboBox, QScrollArea, QFrame, QSpinBox, QDoubleSpinBox, QAbstractSpinBox
from qtpy import QtCore
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
import numpy as np
from CLAnalysis import generate_stimulus, read_response

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Chirplab')
        
        # main GUI structure for navigating between chirp parameters/IO and measurements
        self.tabs = QTabWidget()
        
        # First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
        self.chirp_tab = ChirpTab()
        self.tabs.addTab(self.chirp_tab,'Chirp Stimulus/Response')
        
        layout = QGridLayout() # base layout. Only 0,0 used
        layout.addWidget(self.tabs, 0,0)
        widget = QWidget() # Layout can't be applied directly to QMainWindow, need a base QWidget
        widget.setLayout(layout)
        self.setCentralWidget(widget)

# main recurring gui structure of chirplab. A configuration panel on the left, with a graph area on the right
class CLTab(QSplitter): # base widget is a splitter
    def __init__(self):
        super().__init__()
        
        # configuration panel setup
        self.panel = QVBoxLayout() # base layout for the configuration panel
        panel_scroll = QScrollArea() #QScrollArea and QFrame needed to make the panel scrollable
        panel_scroll.setWidgetResizable(True)
        panel_frame = QFrame(panel_scroll)
        panel_frame.setLayout(self.panel)
        panel_scroll.setWidget(panel_frame)
        self.panel.setAlignment(QtCore.Qt.AlignTop)
                
        # graph area setup
        self.graph = MplCanvas(self)
        self.graph_toolbar = NavigationToolbar(self.graph)
        graph_layout = QVBoxLayout()
        graph_layout.addWidget(self.graph_toolbar)
        graph_layout.addWidget(self.graph)
        graph_area = QWidget()
        graph_area.setLayout(graph_layout)
        
        # set config panel and graph area as elements on either side of splitter
        self.addWidget(panel_scroll)
        self.addWidget(graph_area)
        
        # set initial panel width
        panel_width = 175 # reasonable initial value on my machine. Panel size/scaling will need a lot of work #DPI
        self.setSizes([panel_width, self.window().width()-panel_width])
        
    # add an accordion section to the configuration panel    
    def addPanelSection(self, section_name):
        section = QSection(section_name)
        self.panel.addWidget(section)
        vbox = QSectionVBoxLayout(section)
        section.toggleButton.click()
        return vbox # return the section layout so the caller can add elements to the section

# First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
class ChirpTab(CLTab):
    def __init__(self):
        super().__init__()
        
        # Chirp parameters section
        self.chirp_params = self.addPanelSection('Chirp Parameters')
        
        self.start_freq = CLParamNum('Start Freq', clp.project['start_freq'], 'Hz', 0.01, clp.project['sample_rate']/2)
        self.chirp_params.addWidget(self.start_freq)
        def updateStartFreq(new_value):
            if new_value == self.stop_freq.value: # catch any other invalid values (min/max are caught automatically)
                # don't catch start_freq being higher than stop_freq. Down-swept chirps technically still work with most measurements
                self.start_freq.revert() # revert and do nothing
            else:
                clp.project['start_freq'] = float(new_value) # apply the new value to the project
                self.updateStimulus() # update the stimulus (which updates the measurements)
        self.start_freq.update_callback = updateStartFreq
        
        self.stop_freq = CLParamNum('Stop Freq', clp.project['stop_freq'], 'Hz', 0.01, clp.project['sample_rate']/2)
        self.chirp_params.addWidget(self.stop_freq)
        def updateStopFreq(new_value):
            if new_value == self.start_freq.value:
                self.stop_freq.revert()
            else:
                clp.project['stop_freq'] = float(new_value)
                self.updateStimulus()
        self.stop_freq.update_callback = updateStopFreq
        
        self.chirp_length = CLParamNum('Chirp Length', clp.project['chirp_length'], ['Sec','Samples'], 0.1, 60, 'float')
        self.chirp_params.addWidget(self.chirp_length)
        def updateChirpLength(new_value):
            if self.chirp_length.units.currentIndex() == 0: # update seconds directly
                clp.project['chirp_length'] = self.chirp_length.value
            else: # convert samples to seconds
                clp.project['chirp_length'] = self.chirp_length.value / clp.project['sample_rate']
            self.updateStimulus()
        self.chirp_length.update_callback = updateChirpLength
        def updateChirpLengthUnits(index):
            print(clp.project['chirp_length'])
            if index==0: # seconds
                self.chirp_length.setMinimum(0.1)
                self.chirp_length.setMaximum(60)
                self.chirp_length.setValue(clp.project['chirp_length'])
            else:
                self.chirp_length.setMinimum(0.1*clp.project['sample_rate'])
                self.chirp_length.setMaximum(60*clp.project['sample_rate'])
                self.chirp_length.setValue(clp.project['chirp_length']*clp.project['sample_rate'])
        self.chirp_length.units_update_callback = updateChirpLengthUnits
        
        self.output_params = self.addPanelSection('Output')
        
        
        # Input file or audio device section
        self.input_params = self.addPanelSection('Input')
        
        self.input_mode_dropdown = QComboBox()
        self.input_params.addWidget(self.input_mode_dropdown)
        self.input_mode_dropdown.addItem('File')
        
        self.input_file_box = CLParameter('Input File', clp.project['input']['file'], '')
        self.input_params.addWidget(self.input_file_box)
        
        self.input_channel = CLParameter('Channel', clp.project['input']['channel'], '')
        self.input_params.addWidget(self.input_channel)
        
        self.analyze_button = QPushButton('Analyze')
        self.input_params.addWidget(self.analyze_button)
        self.analyze_button.clicked.connect(self.analyze)
        
        
        # Chirp analysis parameters
        self.analysis_params = self.addPanelSection('Analysis Parameters')
        
        self.sample_rate = CLParameter('Sample Rate', clp.project['sample_rate'], 'Hz')
        self.analysis_params.addWidget(self.sample_rate)
        
        self.pre_sweep = CLParameter('Pre Sweep', clp.project['pre_sweep'], 'Sec')
        self.analysis_params.addWidget(self.pre_sweep)
        
        self.post_sweep = CLParameter('Post Sweep', clp.project['post_sweep'], 'Sec')
        self.analysis_params.addWidget(self.post_sweep)
        
        # plot stimulus/response signals
        self.plot()
        

    def updateStimulus(self):
        # generate new stimulus from chirp and analysis parameters
        generate_stimulus()
        
        # update chirp tab graph
        self.plot()
        
        # update measurements
        print('todo: update all measurements')
        
        
    def analyze(self):
        # read in input file
        read_response() # reads in raw response, gets desired channel, and puts segment containing chirp in clp.signals['stimulus']

        # update chirp tab graph
        self.plot()

        # update measurements
        print('todo: update all measurements')
        
    def plot(self):
        self.graph.axes.cla()
        if self.chirp_length.units.currentIndex() == 0: #times in seconds
            times = np.arange(len(clp.signals['stimulus']))/clp.project['sample_rate']
        else: #times in samples
            times = np.arange(len(clp.signals['stimulus']))
        self.graph.axes.plot(times, clp.signals['stimulus'])
        self.graph.axes.plot(times, clp.signals['response'])
        if any(clp.signals['noise']):
            self.graph.axes.plot(times, clp.signals['noise'])
        self.graph.draw()

# sub class of the VBoxLayout for use in collapsible sections
# sections only update their expanded height when section.setContentLayout() is called
# QSectionVBoxLayout stores a reference to the parent section and updates the section height whenever a new element is added
class QSectionVBoxLayout(QVBoxLayout):
    def __init__(self, section):
        super().__init__()
        self.section = section # keep a reference to the parent section to update when adding elements (not the same as the QT parent object, calling .parent() or .parentWidget() on a regular VBox does not return the containing section)
        
    def addWidget(self, a0):
        super().addWidget(a0)
        self.section.setContentLayout(self) # force containing section to update its expanded height when adding new elements


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
      
        
class CLParamNum(CLParameter):
    # numeric parameter using a spinbox for input and automatic checking of min/max values
    def __init__(self, label_text, parameter_value, unit=None, min_val=float('-inf'), max_val=float('inf'), numtype='float'):
        super().__init__(label_text, parameter_value, unit)
        self.min = min_val
        self.max = max_val
        
        # replace generic text box with spinbox
        self.text_box.setParent(None)
        
        # any single one of these lines (plus the layout.update() call below) removes the text box
        self.layout.removeWidget(self.text_box)
        #self.text_box.deleteLater() # this leads to an error being thrown when entering text into the spinbox
        #self.text_box.close()
        
        # don't actually use Qt's validation. Basic min/max/int checking is easy and changing values/limits of Qt classes fires callbacks and leads to confusing state machine problems
        self.spin_box = QDoubleSpinBox()
        self.spin_box.setMinimum(float('-inf'))
        self.spin_box.setMaximum(float('inf'))
        self.setNumtype(numtype)
        self.layout.insertWidget(1, self.spin_box) # works, but the spinbox doesn't fill the middle the way it would if the spinbox is added directly instead of inserted
        self.layout.update()
        self.spin_box.setValue(float(parameter_value)) # value can only be changed after adding to layout
        def valueChanged(new_val): # can also catch textChanged. textChanged and valueChanged are both called everytime a character is typed, not just editing finished. Might be worth catching textChanged and only validate on editing finished
            if self.numtype == 'int':
                new_val= round(new_val)
            self.value = min(max(new_val, self.min), self.max)
            if not self.update_callback is None:
                self.update_callback(self.value)
            self.last_value = self.value
        self.spin_box.valueChanged.connect(valueChanged)
        
    def set_min(self, new_min):
        self.min = new_min
        
        
    def set_max(self, new_max):
        self.max = new_max
        
    def set_value(self, new_value):
        self.spin_box.setValue(new_value)
        
    def setNumtype(self, new_type):
        # check for valid values, either 'float' or 'int'
        self.numtype = new_type
        if self.numtype == 'float':
            self.spin_box.setStepType(QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
        else: # int
            self.spin_box.setStepType(QAbstractSpinBox.StepType.DefaultStepType)
            # default step value should still be 1
        
        
        
        
        
        
        
        
        
# matplotlib stuff, mostly copied from pythonguis.com
import matplotlib
matplotlib.use('Qt5Agg')

#matplotlib speed settings
matplotlib.style.use('default') # settings are persistent in Spyder. use('default') to reset
# agg.path.chunksize = 0
# path.simplify = True
# path.simplify_threshold = 1/9

#matplotlib.style.use('fast') # fast, but sometimes leaves holes in stimulus/response plots. Equivalent to:
# agg.path.chunksize = 10000
# path.simplify = True
# path.simplify_threshold = 1.0

# chunksize and simplify_threshold have some interdependency. Increasing one or the other is fine, marginally improves performance. Increasing both improves performance more but introduces artefacts.
matplotlib.rcParams['agg.path.chunksize'] = 100
matplotlib.rcParams['path.simplify'] = True
matplotlib.rcParams['path.simplify_threshold'] = 1.0

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100): # DPI doesn't seem to make artefacts better/worse, Qt or actual display DPI might.
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
