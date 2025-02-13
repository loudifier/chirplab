from qtpy.QtWidgets import QSplitter, QVBoxLayout, QScrollArea, QFrame, QWidget
from qtpy import QtCore
import pyqtgraph as pg
from CLGui import EngAxisItem

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
        self.graph = pg.PlotWidget(axisItems={'bottom':EngAxisItem('bottom')})
        self.graph.showGrid(True, True, 0.25)
        self.graph.addLegend(brush=pg.mkBrush(255,255,255,192))
        graph_layout = QVBoxLayout()
        graph_layout.addWidget(self.graph)
        graph_area = QWidget()
        graph_area.setLayout(graph_layout)
        
        # set config panel and graph area as elements on either side of splitter
        self.addWidget(panel_scroll)
        self.addWidget(graph_area)
        
        # set initial panel width
        panel_width = 200 # todo: reasonable initial value on my machine. Panel size/scaling will need a lot of work #DPI
        self.setSizes([panel_width, self.window().width()-panel_width])