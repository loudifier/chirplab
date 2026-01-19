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
        tick_strings = [str(EngNumber(value*1)) for value in (10 ** np.array(values).astype(float) * np.array(scale))]
        if (EngNumber(tick_strings[-1]) / EngNumber(tick_strings[0])) > 10:
            # for any plots that show more than 1 decade of data, only show numbers starting with 1, 2, or 5
            tick_strings = [tick if (tick[0] in ['1', '2', '5']) else '' for tick in tick_strings]
        return tick_strings
    
    # todo: also handle linear ticks
    
    
    
class QHSeparator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)



from CLGui.Undo import undo_stack
from CLGui.CLTab import CLTab
from CLGui.CLParameter import CLParameter, CLParamNum, CLParamDropdown, CLParamFile, FreqPointsParams
from CLGui.QCollapsible.QCollapsible import QCollapsible
from CLGui.CalibrationDialog import CalibrationDialog
from CLGui.ChirpTab import ChirpTab
from CLGui.MainWindow import MainWindow