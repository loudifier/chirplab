from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QSplitter, QTextEdit
from qtpy import QtCore
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
import matplotlib.pyplot as plt

# main gui element of chirplab. A configuration panel on the left, with a graph area on the right
class CLTab(QSplitter): # base widget is a splitter
    def __init__(self, project):
        super().__init__()
        self.project = project
        
        self.panel = QVBoxLayout() # base layout for the configuration panel
        self.panel_widget = QWidget()
        self.panel_widget.setLayout(self.panel)
        self.panel.setAlignment(QtCore.Qt.AlignTop)
        
        
        self.graph = QLabel('graph area') # matplotlib axes
        
        
        self.addWidget(self.panel_widget)
        self.addWidget(self.graph)
        
    # add an accordion section to the configuration panel    
    def addPanelSection(self, section_name):
        section = QSection(section_name)
        self.panel.addWidget(section)
        vbox = QSectionVBoxLayout(section)
        return vbox # return the section layout so the caller can add elements to the section

# super class of the VBoxLayout for use in collaptible sections
# sections only update their expanded height when section.setContentLayout() is called
# QSectionVBoxLayout stores a reference to the parent section and updates the section height whenever a new element is added
class QSectionVBoxLayout(QVBoxLayout):
    def __init__(self, section):
        super().__init__()
        self.section = section # keep a reference to the parent section to update when adding elements (not the same as the QT parent object, calling .parent() or .parentWidget() on a regular VBox does not return the containing section)
        
    def addWidget(self, a0):
        super().addWidget(a0)
        self.section.setContentLayout(self) # force containing section to update its expanded height when adding new elements