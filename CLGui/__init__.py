from CLGui.CLTab import CLTab
from CLGui.CLParameter import CLParameter, CLParamNum

# remove all plots from a graph without removing title, labels, etc.
def clear_plot(axes):
    # manually remove all artists (line or surface plots)
    for artist in axes.lines + axes.collections:
        artist.remove()
    
    # reset color for new plots
    axes.set_prop_cycle(None)
    
    

from qtpy.QtWidgets import QMainWindow, QTabWidget, QGridLayout, QWidget
from CLGui.ChirpTab import ChirpTab

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
        

