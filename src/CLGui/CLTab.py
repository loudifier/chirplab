from qtpy.QtWidgets import QSplitter, QVBoxLayout, QScrollArea, QFrame, QWidget, QApplication
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

        # catch all mouse scrolls in panel area and don't pass on to children
        # allows you to scroll without accidentally changing dropdowns, spinbox values, etc.
        self.scroll_handler = ScrollHandler(panel_frame) # panel_frame is the object that actually handles the scroll events
        QApplication.instance().installEventFilter(self.scroll_handler) # could install filters on all child objects, but filtering the whole application seems to be the only way to reliably catch all scroll events
                
        # graph area setup
        self.graph = pg.PlotWidget(axisItems={'bottom':EngAxisItem('bottom')})
        self.graph.showGrid(True, True, 0.25)
        self.graph.legend = self.graph.addLegend(brush=pg.mkBrush(255,255,255,192))
        graph_layout = QVBoxLayout()
        graph_layout.addWidget(self.graph)
        graph_area = QWidget()
        graph_area.setLayout(graph_layout)
        
        # set config panel and graph area as elements on either side of splitter
        self.addWidget(panel_scroll)
        self.addWidget(graph_area)
        
        # set initial panel width
        panel_width = 235 # todo: reasonable initial value on my machine. Panel size/scaling will need a lot of work #DPI
        self.setSizes([panel_width, self.window().width()-panel_width])


class ScrollHandler(QtCore.QObject):
    def __init__(self, scroll_panel):
        super().__init__()
        self.scroll_panel = scroll_panel

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Wheel: # some other events should probably also be caught. Still activates widgets when you scroll past them
            if self.is_in_scroll_panel(obj):
                QtCore.QCoreApplication.sendEvent(self.scroll_panel, event)
                return True
        return super().eventFilter(obj, event)
    
    def is_in_scroll_panel(self, obj):
        parent = obj.parent()
        while parent is not None:
            if parent is self.scroll_panel:
                return True
            parent = parent.parent()
        return False