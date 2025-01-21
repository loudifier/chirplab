from qtpy.QtWidgets import QSplitter, QVBoxLayout, QScrollArea, QFrame, QWidget
from qtpy import QtCore
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section

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