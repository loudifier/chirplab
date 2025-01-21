import CLProject as clp
from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSplitter, QLineEdit, QComboBox
from qtpy import QtCore
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
from scipy.io import wavfile
import numpy as np
from CLAnalysis import logchirp

# main gui element of chirplab. A configuration panel on the left, with a graph area on the right
class CLTab(QSplitter): # base widget is a splitter
    def __init__(self):
        super().__init__()
        
        self.panel = QVBoxLayout() # base layout for the configuration panel
        self.panel_widget = QWidget()
        self.panel_widget.setLayout(self.panel)
        self.panel.setAlignment(QtCore.Qt.AlignTop)
        
        
        self.graph = MplCanvas(self)
        self.graph_toolbar = NavigationToolbar(self.graph)
        graph_layout = QVBoxLayout()
        graph_layout.addWidget(self.graph_toolbar)
        graph_layout.addWidget(self.graph)
        graph_area = QWidget()
        graph_area.setLayout(graph_layout)
        
        self.addWidget(self.panel_widget)
        self.addWidget(graph_area)
        
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
        
        self.start_freq = CLParameter('Start Freq', clp.project['start_freq'], 'Hz')
        self.chirp_params.addWidget(self.start_freq)
        def updateStartFreq():
            new_value = self.start_freq.text_box.text() # get text entered to text box
            if new_value.isnumeric() and float(new_value)>0 and float(new_value)<=(clp.project['sample_rate']/2): # make sure new value is a number greater than 0 and less than or equal to Nyquist
                self.start_freq.last_value = new_value # if new value is valid, use the new value
                clp.project['start_freq'] = float(new_value) # apply the new value to the project
                self.updateStimulus() # update the stimulus (which updates the measurements)
            else:
                self.start_freq.text_box.setText(self.start_freq.last_value) # if new value is not valid, revert to the previous value and do nothing
        self.start_freq.text_box.editingFinished.connect(updateStartFreq)
        
        self.stop_freq = CLParameter('Stop Freq', clp.project['stop_freq'], 'Hz')
        self.chirp_params.addWidget(self.stop_freq)
        
        self.chirp_length = CLParameter('Chirp Length', clp.project['chirp_length'], 'Sec')
        self.chirp_params.addWidget(self.chirp_length)
        
        
        
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
        

    def updateStimulus(self):
        # generate new stimulus from chirp and analysis parameters
        clp.signals['stimulus'] = np.concatenate((
            np.zeros(round(clp.project['pre_sweep']*clp.project['sample_rate'])),
            logchirp(clp.project['start_freq'], clp.project['stop_freq'], clp.project['chirp_length'], clp.project['sample_rate']),
            np.zeros(round(clp.project['post_sweep']*clp.project['sample_rate']))))
        # update chirp tab graph
        self.graph.axes.cla()
        self.graph.axes.plot(np.arange(len(clp.signals['stimulus']))/clp.project['sample_rate'],clp.signals['stimulus'])
        self.graph.draw()
        # update measurements
        
    def analyze(self):
        # read in input file
        rate, samples = wavfile.read(clp.project['input']['file'])
        self.graph.axes.cla()
        self.graph.axes.plot(samples)
        self.graph.draw()
        # align and trim response signal
        # update measurements with new response

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


# combination class for displaying and entering configuration parameters
# label on the left, text box in the middle, and a unit label on the right (right label to be expanded later to use a drop down for units, checkbox, etc.)
class CLParameter(QWidget):
    def __init__(self, label_text, parameter_value, unit):
        super().__init__()
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        
        self.label = QLabel(label_text)
        self.layout.addWidget(self.label)
        
        self.text_box = QLineEdit(str(parameter_value))
        self.last_value = str(parameter_value) # keep track of last value, to revert back to in case new entry fails data validation
        self.layout.addWidget(self.text_box)
        
        self.unit = QLabel(unit)
        self.layout.addWidget(self.unit)
        
        
        
        
        
        
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
