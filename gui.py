from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSplitter, QTextEdit, QComboBox
from qtpy import QtCore
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
from scipy.io import wavfile


# main gui element of chirplab. A configuration panel on the left, with a graph area on the right
class CLTab(QSplitter): # base widget is a splitter
    def __init__(self, project):
        super().__init__()
        self.project = project
        
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
    def __init__(self, project):
        super().__init__(project)
        self.project = project
        
        self.chirp_params = self.addPanelSection('Chirp Parameters')
        self.start_freq = CLParameter('Start Freq', self.project['start_freq'], 'Hz') ; self.chirp_params.addWidget(self.start_freq)
        self.stop_freq = CLParameter('Stop Freq', self.project['stop_freq'], 'Hz') ; self.chirp_params.addWidget(self.stop_freq)
        self.chirp_length = CLParameter('Chirp Length', self.project['chirp_length'], 'Sec') ; self.chirp_params.addWidget(self.chirp_length)
        
        self.output_params = self.addPanelSection('Output')
        
        self.input_params = self.addPanelSection('Input')
        self.input_mode_dropdown = QComboBox() ; self.input_params.addWidget(self.input_mode_dropdown)
        self.input_mode_dropdown.addItem('File')
        self.input_file_box = CLParameter('Input File', self.project['input']['file'], '') ; self.input_params.addWidget(self.input_file_box)
        self.input_channel = CLParameter('Channel', 1, '') ; self.input_params.addWidget(self.input_channel)
        self.analyze_button = QPushButton('Analyze') ; self.input_params.addWidget(self.analyze_button)
        self.analyze_button.clicked.connect(self.analyze)
        
        
    
    def analyze(self):
        # read in input file
        rate, samples = wavfile.read(self.project['input']['file'])
        print('analyze')
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
        
        self.text_box = QTextEdit(str(parameter_value))
        self.layout.addWidget(self.text_box)
        
        self.unit = QLabel(unit)
        self.layout.addWidget(self.unit)
        
        
        
        
        
        
        
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
