import CLProject as clp
from qtpy.QtWidgets import QDialog, QVBoxLayout, QMessageBox, QCheckBox, QHBoxLayout, QFrame, QPushButton
from CLGui import CLTab, CLParamFile, CLParamNum, CLParameter, QHSeparator
from CLAnalysis import audio_file_info, read_audio_file
import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt
from scipy.fftpack import fft, fftfreq
from scipy.signal.windows import hann
from Biquad import Biquad, bandpass_coeff

class CalibrationDialog(QDialog):
    def __init__(self, chirp_tab):
        super().__init__()

        self.setWindowTitle('Input Calibration')
        
        # todo: figure out how to not have a window icon

        tab = CLTab() # same overall structure as a measurement tab - parameter panel on the left with a gaph on the right
        layout = QVBoxLayout(self)
        layout.addWidget(tab)
        tab_sizes = tab.sizes()
        tab.setSizes([350, tab_sizes[1] + tab_sizes[0] - 350])

        tab.graph.scene().removeItem(tab.graph.legend)

        self.samples = []

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

                skip.max = len(self.samples) - 2
                skip.set_value(min(skip.value, skip.max))

                measure()
            file.update_callback = update_file

            def measure(_=None):
                if not len(self.samples):
                    return
                
                self.times = np.arange(len(self.samples)) / self.file_info['sample_rate']
                noise_pen = pg.mkPen(color=clp.NOISE_COLOR, width=clp.PLOT_PEN_WIDTH)
                tab.graph.plot(self.times, self.samples, pen=noise_pen)

                start_sample = round(skip.value * self.file_info['sample_rate'])
                end_sample = min(start_sample + round(length.value * self.file_info['sample_rate']), len(self.samples)-1)
                measure_samples = self.samples.copy()

                # apply filtering
                if bandpass.isChecked():
                    if auto.isChecked():
                        spectrum = fft(measure_samples * hann(len(measure_samples)))
                        freqs = fftfreq(len(measure_samples), 1/self.file_info['sample_rate'])
                        spectrum *= freqs # correct for noise spectrum likely having 1/f shape. Helps avoid detecting very low rumble when cal tone level is relatively low. todo: look into tone prominence ratio or something more sophisticated at some point.
                        frequency.set_value(freqs[np.argmax(np.abs(spectrum))])

                    b, a = bandpass_coeff(frequency.value, 2, self.file_info['sample_rate']) # Q=10 results in 24dB sidetone rejection at +/-1 octave
                    filt = Biquad(b, a)
                    measure_samples = filt.process(measure_samples)

                measure_pen = pg.mkPen(color=clp.PLOT_COLORS[0], width=clp.PLOT_PEN_WIDTH)
                tab.graph.plot(self.times[start_sample:end_sample], measure_samples[start_sample:end_sample], pen=measure_pen)

                # measure signal
                rms = np.sqrt(np.mean(measure_samples[start_sample:end_sample]**2))
                rms *= np.sqrt(2) # apply 3dB sine wave correction
                if tone_level.units.currentIndex():
                    tone_level.set_value(str(rms))
                else:
                    tone_level.set_value(str(20*np.log10(rms)))
            

            skip = CLParamNum('Skip first', 0, 'Sec', 0, numtype='float')
            tab.panel.addWidget(skip)
            skip.update_callback = measure

        length = CLParamNum('Measurement length', 1, 'Sec', 0.1, numtype='float')
        tab.panel.addWidget(length)
        length.update_callback = measure

        bandpass = QCheckBox('Bandpass filter')
        bandpass.stateChanged.connect(measure)
        auto = QCheckBox('Auto')
        auto.setChecked(True)
        def update_auto(checked):
            frequency.spin_box.setEnabled(not checked)
            measure()
        auto.stateChanged.connect(update_auto)
        checkboxes = QFrame()
        checkbox_layout = QHBoxLayout(checkboxes)
        checkbox_layout.addWidget(bandpass)
        checkbox_layout.addWidget(auto)
        tab.panel.addWidget(checkboxes)

        frequency = CLParamNum('Frequency', 1000, 'Hz', 1, 20000, 'float')
        frequency.spin_box.setEnabled(False)
        tab.panel.addWidget(frequency)
        frequency.update_callback = measure

        tab.panel.addWidget(QHSeparator())

        tone_level = CLParameter('Measured tone level', '0', ['dBFS', 'FS'])
        tone_level.text_box.setEnabled(False)
        tab.panel.addWidget(tone_level)

        tab.panel.addWidget(QHSeparator())

        FS_per_Pa = CLParamNum('Acoustic calibration', clp.project['FS_per_Pa'], 'FS/Pa', numtype='float') # todo: set reasonable minimum
        FS_per_Pa.spin_box.setDecimals(6)
        tab.panel.addWidget(FS_per_Pa)

        acoustic_level = CLParamNum('Reference level', 1.0, ['Pa', 'dBSPL'], 0.00002, numtype='float') # 0dBSPL minimum
        tab.panel.addWidget(acoustic_level)
        def update_acoustic_units(index):
            ninety_four_dBSPL = 20*np.log10(1/0.00002) # 0dBSPL = 20uPa
            if index:
                acoustic_level.min = 0
                acoustic_level.set_value(20*np.log10(acoustic_level.value) + ninety_four_dBSPL)
            else:
                acoustic_level.min = 0.00002
                acoustic_level.set_value(10**((acoustic_level.value - ninety_four_dBSPL)/20))
        acoustic_level.units_update_callback = update_acoustic_units

        set_acoustic = QPushButton('Set acoustic calibration')
        tab.panel.addWidget(set_acoustic)
        def set_FS_per_Pa():
            if float(tone_level.value) != 0:
                if tone_level.units.currentIndex():
                    FS = float(tone_level.value)
                else:
                    FS = 10**(float(tone_level.value)/20)
                if acoustic_level.units.currentIndex():
                    Pa = 10**(acoustic_level.value/20)
                else:
                    Pa = acoustic_level.value
                FS_per_Pa.set_value(FS / Pa)
                update_V_per_Pa()
        set_acoustic.clicked.connect(set_FS_per_Pa)
        
        tab.panel.addWidget(QHSeparator())

        FS_per_V = CLParamNum('Electrical calibration', clp.project['FS_per_V'], 'FS/V', numtype='float') # todo: set reasonable minimum
        FS_per_V.spin_box.setDecimals(6)
        tab.panel.addWidget(FS_per_V)

        electrical_level = CLParamNum('Reference level', 1.0, ['V', 'dBV'], 0.000001, numtype='float') # 1uV minimum
        tab.panel.addWidget(electrical_level)
        def update_electrical_units(index):
            if index:
                electrical_level.min = 20*np.log10(0.000001)
                electrical_level.set_value(20*np.log10(electrical_level.value))
            else:
                electrical_level.min = 0.000001
                electrical_level.set_value(10**(electrical_level.value/20))
        electrical_level.units_update_callback = update_electrical_units

        set_electrical = QPushButton('Set electical calibration')
        tab.panel.addWidget(set_electrical)
        def set_FS_per_V():
            if float(tone_level.value) != 0:
                if tone_level.units.currentIndex():
                    FS = float(tone_level.value)
                else:
                    FS = 10**(float(tone_level.value)/20)
                if electrical_level.units.currentIndex():
                    V = 10**(electrical_level.value/20)
                else:
                    V = electrical_level.value
                FS_per_V.set_value(FS / V)
                update_V_per_Pa()
        set_electrical.clicked.connect(set_FS_per_V)

        tab.panel.addWidget(QHSeparator())

        V_per_Pa = CLParameter('Electroacoustic sensitivity', str(0), 'V/Pa')
        V_per_Pa.text_box.setEnabled(False)
        tab.panel.addWidget(V_per_Pa)
        def update_V_per_Pa(_=None):
            V_per_Pa.set_value(str(round((1/FS_per_V.value) / (1/FS_per_Pa.value), 4)))
        update_V_per_Pa()
        FS_per_Pa.update_callback = update_V_per_Pa
        FS_per_V.update_callback = update_V_per_Pa

        tab.panel.addWidget(QHSeparator())

        save = QPushButton('Save calibration')
        def save_cal():
            clp.project['FS_per_Pa'] = FS_per_Pa.value
            chirp_tab.input_params.FS_per_Pa.set_value(FS_per_Pa.value)
            clp.project['FS_per_V'] = FS_per_V.value
            chirp_tab.input_params.FS_per_V.set_value(FS_per_V.value)
            self.accept()
        save.clicked.connect(save_cal)
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        buttons = QFrame()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.addWidget(save)
        buttons_layout.addWidget(cancel)
        tab.panel.addWidget(buttons)

    def keyPressEvent(self, event):
        # keep QDialog from just pushing the first button it finds when the user hits Enter
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            return
