import CLProject as clp
from qtpy.QtWidgets import QDialog, QVBoxLayout, QMessageBox, QCheckBox, QHBoxLayout, QFrame, QPushButton
from CLGui import CLTab, CLParamFile, CLParamNum, CLParameter, QHSeparator
from CLAnalysis import audio_file_info, read_audio_file

class CalibrationDialog(QDialog):
    def __init__(self, chirp_tab):
        super().__init__()

        self.setWindowTitle('Input Calibration')
        
        # todo: figure out how to not have a window icon

        tab = CLTab() # same overall structure as a measurement tab - parameter panel on the left with a gaph on the right
        layout = QVBoxLayout(self)
        layout.addWidget(tab)

        if clp.project['input']['mode'] == 'file':
            file = CLParamFile('Calibration tone file', '')
            file.mime_types = ['audio/wav', 'application/octet-stream']
            tab.panel.addWidget(file)
            def update_file(file_path):
                self.file_info = audio_file_info(file_path)
                if clp.project['input']['channel'] > self.file_info['channels']:
                    message = QMessageBox()
                    message.setIcon(QMessageBox.Information) # todo: figure out how to not show the window icon
                    message.setWindowTitle('Channel mismatch')
                    message.setText('Channel ' + str(clp.project['input']['channel']) + ' selected but calibration tone file only contains ' + str(file_info['channels']) + ' channel' + 's'*int(file_info['channels']>1) + '. Measuring signal in channel 1 instead.')
                    message.exec()

                    channel = 1
                else:
                    channel = clp.project['input']['channel']

                self.samples = read_audio_file(file_path)
                if self.file_info['channels'] > 1:
                    self.samples = self.samples[:, channel]

                # update max skip
                # update skip (which should ultimately call measure())

            def measure():
                self.times = np.arange(len(self.samples)) * self.file_info['sample_rate']
                tab.graph.plot(self.times, self.samples)

                start_sample = round(skip.value * self.file_info['start_sample'])
                end_sample = min(start_sample + round(length.value * self.file_info['sample_rate']), len(self.samples)-1)


            file.update_callback = update_file

            skip = CLParamNum('Skip first', 0, 'Sec', 0, numtype='float')
            tab.panel.addWidget(skip)

        length = CLParamNum('Measurement length', 1, 'Sec', 0.1, numtype='float')
        tab.panel.addWidget(length)

        bandpass = QCheckBox('Bandpass filter')
        auto = QCheckBox('Auto')
        auto.setChecked(True)
        checkboxes = QFrame()
        checkbox_layout = QHBoxLayout(checkboxes)
        checkbox_layout.addWidget(bandpass)
        checkbox_layout.addWidget(auto)
        tab.panel.addWidget(checkboxes)

        frequency = CLParamNum('Frequency', 1000, 'Hz', 1, 20000, 'float')
        frequency.spin_box.setEnabled(False)
        tab.panel.addWidget(frequency)

        tab.panel.addWidget(QHSeparator())

        tone_level = CLParameter('Measured tone level', str(0), ['dBFS', 'FS'])
        tone_level.text_box.setEnabled(False)
        tab.panel.addWidget(tone_level)

        FS_per_Pa = CLParamNum('Acoustic calibration', clp.project['FS_per_Pa'], 'FS/Pa', numtype='float') # todo: set reasonable minimum
        tab.panel.addWidget(FS_per_Pa)

        acoustic_level = CLParamNum('Reference level', 1.0, ['Pa', 'dBSPL'], 0.00002, numtype='float')
        tab.panel.addWidget(acoustic_level)
        
        tab.panel.addWidget(QHSeparator())

        FS_per_V = CLParamNum('Electrical calibration', clp.project['FS_per_V'], 'FS/V', numtype='float') # todo: set reasonable minimum
        tab.panel.addWidget(FS_per_V)

        electrical_level = CLParamNum('Reference level', 1.0, ['V', 'dBV'], 0.000001, numtype='float')
        tab.panel.addWidget(electrical_level)

        tab.panel.addWidget(QHSeparator())

        save = QPushButton('Save calibration')
        cancel = QPushButton('Cancel')
        buttons = QFrame()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.addWidget(save)
        buttons_layout.addWidget(cancel)
        tab.panel.addWidget(buttons)


