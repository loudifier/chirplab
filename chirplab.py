from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QTabWidget, QLabel, QPushButton, QVBoxLayout, QSplitter
from qt_collapsible_section.Section import Section as QSection # accordion-type widget from https://github.com/RubendeBruin/qt-collapsible-section
import matplotlib.pyplot as plt

import sys

def main(args = sys.argv):
    app = QApplication(args)
    
    window = MainWindow()
    window.show()
    
    app.exec()



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Chirplab')
        
        layout = QGridLayout() # base layout. Only 0,0 used
        tabs = QTabWidget() # main GUI structure for navigating between chirp parameters/IO and measurements
        
        # First tab - Chirp parameters, input/output, time-domain view of stimulus and response waveforms
        chirp_graph = QLabel('chirp stimulus/response time-domain graph area')
        chirp_setup_panel = QVBoxLayout()
        chirp_setup_panel.addWidget(QLabel('blarg'))
        chirp_setup_panel.addWidget(QLabel('honk'))
        #chirp_setup_widget = QWidget()
        #chirp_setup_widget.setLayout(chirp_setup_panel)
        chirp_setup_widget = QSection('Chirp Parameters')
        chirp_setup_widget.setContentLayout(chirp_setup_panel)
        chirp_split = QSplitter()
        chirp_split.addWidget(chirp_setup_widget)
        chirp_split.addWidget(chirp_graph)
        tabs.addTab(chirp_split, 'Chirp setup/capture')
        
        label2 = QLabel('tab2')
        tabs.addTab(label2, 'Frequency Response')
        
        
        
        
        layout.addWidget(tabs, 0,0)
        widget = QWidget() # Layout can't be applied directly to QMainWindow, need a base QWidget
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        
    def button_clicked(self):
        if self.button.isChecked():
            self.button.setText('on')
        else:
            self.button.setText('off')
            
            
            
            
# class Window(QWidget):
#     def __init__(self):
#         QWidget.__init__(self)
#         layout = QGridLayout()
#         self.setLayout(layout)
#         label1 = QLabel("Widget in Tab 1.")
#         label2 = QLabel("Widget in Tab 2.")
#         tabwidget = QTabWidget()
#         tabwidget.addTab(label1, "Tab 1")
#         tabwidget.addTab(label2, "Tab 2")
#         layout.addWidget(tabwidget, 0, 0)

# app = QApplication(sys.argv)
# screen = Window()
# screen.show()
# sys.exit(app.exec_())
        
main()