import CLProject as clp
import pyqtgraph as pg
from engineering_notation import EngNumber
import numpy as np
from qtpy.QtWidgets import QFrame

pg.setConfigOption('background', clp.GRAPH_BG)
pg.setConfigOption('foreground', clp.GRAPH_FG)


# version of the pyqtgraph AxisItem that formats ticks with engineering notation prefixes (1e4 -> 10k)
class EngAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.textAngle = kwargs.get('textAngle', 0) # add option to rotate x axis tick strings like here: https://github.com/pyqtgraph/pyqtgraph/issues/322
    
    def logTickStrings(self, values, scale, spacing):
        return [str(EngNumber(value*1)) for value in (10 ** np.array(values).astype(float) * np.array(scale))]
    
    
    
class QHSeparator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)



from CLGui.CLTab import CLTab
from CLGui.CLParameter import CLParameter, CLParamNum, CLParamDropdown, CLParamFile
from CLGui.QCollapsible.QCollapsible import QCollapsible
from CLGui.MainWindow import MainWindow