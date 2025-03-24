import CLProject as clp
from CLAnalysis import freq_points, interpolate, resample, find_offset
from CLGui import CLParamDropdown, FreqPointsParams
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal.windows import hann
import numpy as np
from CLMeasurements import CLMeasurement
from scipy.stats import linregress
from qtpy.QtWidgets import QCheckBox

# good resource about phase and group delay: http://cjs-labs.com/sitebuildercontent/sitebuilderfiles/GroupDelay.pdf

class PhaseResponse(CLMeasurement):
    measurement_type_name = 'Phase Response'
    
    TIMING_MODES = ['absolute', 'relative']
    OUTPUT_UNITS = ['degrees', 'radians']
    
    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)
        self.params['type'] = 'PhaseResponse'

        if len(params)<3: # populate default measurement parameters if none are provided
            # add new keys to existing dict instead of defining new one, so updates will propogate to full project dict and can be easily saved to a project file
            self.params['mode'] = 'excess' # options are 'excess' which attempts to find the effective phase assuming 0Hz phase is 0 or -180 degrees, and 'relative' which uses a loopback channel as the t=0 reference
            self.params['excess_method'] = 'linear_phase' # options are 'linear_phase' which aligns to a linear regression of the phase over the chirp, 'min_delay' which aligns phase to an estimate of the minimum group delay, and 'cross_correlation' which uses the time alignment determined by cross correlation when reading the input signal
            self.params['ref_channel'] = 2 # loopback input channel used as the phase reference in 'relative' mode. If there is no input channel ref_channel or ref_channel is the same as the project input channel the measurement will output -1 for all frequency points
            self.params['unwrap'] = True # if true measurement will attempt to unwrap the phase to be continuous instead of the intermediary calculated values, which are bound to +/-180deg (+/-pi). Can easily skip full cycles at high frequencies and technically only absolute assuming receiver/mic is within 1 wavelength of source/speaker at starting chirp frequency.
            self.params['auto_invert'] = False # automatically subtract 180 degrees from phase if lowest chirp frequency is within +/-45 degrees of 180 or -180 degrees

            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'degrees',
                'min_freq': 20,
                'min_auto': True,
                'max_freq': 20000,
                'max_auto': True,
                'spacing': 'octave',
                'num_points': 12,
                'round_points': False}
        
        # update min/max output frequencies if they are set to auto
        if self.params['output']['min_auto']:
            self.params['output']['min_freq'] = self.calc_auto_min_freq()
        if self.params['output']['max_auto']:
            self.params['output']['max_freq'] = self.calc_auto_max_freq()
            
            
    def measure(self):
        # calculate bin frequencies for the FFTs that will be used
        freqs = fftfreq(len(clp.signals['stimulus']), 1/clp.project['sample_rate'])
        # trim to only positive frequencies
        freqs = freqs[1:round(len(freqs)/2)]

        # find the minimum and maximum bins that cover the frequency range of the chirp, used for auto_invert, min_delay and linear_phase
        min_bin = np.argmin(np.abs(freqs - clp.project['start_freq'])) + 1
        max_bin = np.argmin(np.abs(freqs - clp.project['stop_freq'])) - 1

        # apply an aggressive window to the impulse response. Significantly reduces noise but does not impact low frequency phase accuracy as much as magnitude. Used for excess and relative phase modes. Might be overly smooth
        # todo: window width determined empirically, experiment with other widths or exposing as a measurement parameter. Current implementation usually resolves phase at lowest chirp freq to nearest pi
        window_width = round(clp.project['sample_rate'] / clp.project['start_freq'])
        window = np.zeros(len(clp.signals['stimulus']))
        window[:window_width] = hann(window_width)
        window = np.roll(window, -round(window_width/2)) # hann window of width equal to lowest chirp wavelength, centered at t0.

        if self.params['mode']=='excess': # estimate the minimum group delay and apply an offset to the phase
            # calculate raw impulse response
            impulse_response = ifft(fft(clp.signals['response']) / fft(clp.signals['stimulus']))

            # apply window
            impulse_response *= window

            # calculate phase from windowed impulse response (and trim to positive frequencies)
            wrapped_phase_rad = np.angle(fft(impulse_response)[1:len(freqs)+1])

            phase_offset_deg = 0 # no group delay correction, used in the cross_correlation case

            if self.params['excess_method']=='linear_phase':
                # perform a linear regression to determine the linear phase delay over the chirp range
                result = linregress(freqs[min_bin:max_bin], np.rad2deg(np.unwrap(wrapped_phase_rad[min_bin:max_bin]))) # regression over linear frequency scale is weighted toward high frequencies, which works well for this method
                phase_offset_deg = -freqs*result.slope
            
            elif self.params['excess_method']=='min_delay':
                # start with unwrapped phase in degrees
                unwrapped_phase_deg = np.rad2deg(np.unwrap(wrapped_phase_rad))
            
                # calculate group delay from phase
                delay = -(np.roll(unwrapped_phase_deg,-1)-np.roll(unwrapped_phase_deg,1))/(360*freqs[1])

                # get group delay on a log frequency scale (otherwise min calculation will be overly influenced by noisy high frequencies)
                log_freqs = freq_points(freqs[min_bin], freqs[max_bin], round(96*np.log2(clp.project['stop_freq']/clp.project['start_freq']))) # 96 points per octave
                log_delay = interpolate(freqs, delay, log_freqs)

                # get an estimate of the minimum group delay
                min_delay = np.percentile(log_delay,10) # 10th percentile helps reject noisy spikes that are not fully smoothed by IR windowing, also still reasonably acccurate for most electrical/purely digital measurements where minimum delay is at max frequency

                # calculate phase offsets
                phase_offset_deg = min_delay * freqs * 360

            # calculate phase and apply offset
            phase = np.rad2deg(np.unwrap(wrapped_phase_rad))
            phase += phase_offset_deg
            
            if not self.params['unwrap']: # phase offset is continuous, need to re-wrap phase
                phase = (phase + 180) % 360 - 180
        
        else: # phase relative to a loopback reference channel
            if self.params['ref_channel'] > clp.IO['input']['channels'] or self.params['ref_channel'] == clp.project['input']['channel']:
                # selected reference channel is not valid, return all -1
                phase = np.ones(len(freqs)) * -1
                if self.params['output']['unit']=='radians':
                    phase = np.rad2deg(phase) # make output also return -1 radians

            else: # calculate phase relative to reference channel
                # align and trim reference channel from raw response (same process as CLAnalysis.read_response())
                # get the input channel and the reference channel
                response = clp.signals['raw_response'][:,clp.project['input']['channel']-1]
                reference = clp.signals['raw_response'][:,self.params['ref_channel']-1]

                # resample input if necessary
                if clp.project['sample_rate'] != clp.IO['input']['sample_rate']:
                    if clp.project['use_input_rate']:
                        clp.project['sample_rate'] = clp.IO['input']['sample_rate']
                    else:
                        response = resample(response, clp.IO['input']['sample_rate'], clp.project['sample_rate'])
                        reference = resample(reference, clp.IO['input']['sample_rate'], clp.project['sample_rate'])
                    
                # determine the position of the captured chirp in the response signal
                response_delay = find_offset(response, clp.signals['stimulus'])
                
                # pad the response if the beginning or end of the chirp is cut off or there isn't enough silence for pre/post sweep (or there is a severe mismatch between stimulus and response). Throw a warning?
                start_padding = max(0, -response_delay) # response_delay should be negative if beginning is cut off
                response_delay = response_delay + start_padding
                end_padding = max(0, len(clp.signals['stimulus']) - (len(response) - response_delay))
                response = np.concatenate([np.zeros(start_padding),
                                        response,
                                        np.zeros(end_padding)])
                reference = np.concatenate([np.zeros(start_padding),
                                        reference,
                                        np.zeros(end_padding)])
                
                # trim the raw response to just the segment aligned with the stimulus
                response = response[response_delay:response_delay + len(clp.signals['stimulus'])] # get only the part of the raw response signal where the chirp was detected
                reference = reference[response_delay:response_delay + len(clp.signals['stimulus'])]

                # calculate the impulse response between the input channel and reference channel
                impulse_response = ifft(fft(response) / fft(reference))

                # apply window to impulse response
                impulse_response *= window

                # calculate phase from windowed impulse response (and trim to positive frequencies)
                wrapped_phase_rad = np.angle(fft(impulse_response)[1:len(freqs)+1])

                # unwrap and convert to degrees
                if self.params['unwrap']:
                    phase = np.rad2deg(np.unwrap(wrapped_phase_rad))
                else:
                    phase = np.rad2deg(wrapped_phase_rad)

        if self.params['auto_invert']:
            if abs(phase[min_bin] - 180) < 45:
                phase -= 180
            elif abs(phase[min_bin] + 180) < 45:
                phase += 180

            

        # generate array of output frequency points
        self.out_freqs = freq_points(self.params['output']['min_freq'], 
                                     self.params['output']['max_freq'],
                                     self.params['output']['num_points'],
                                     self.params['output']['spacing'],
                                     self.params['output']['round_points'])
        
        # interpolate output points
        self.out_points = interpolate(freqs, phase, self.out_freqs, self.params['output']['spacing']=='linear')
        
        # convert output to desired units
        if self.params['output']['unit'] == 'radians':
            self.out_points = np.deg2rad(self.out_points)
        
        
        
    def init_tab(self):
        super().init_tab()

        # timing mode dropdown
        self.mode = CLParamDropdown('Timing mode', ['excess phase', 'relative phase'])
        if self.params['mode'] == 'relative':
            self.mode.dropdown.setCurrentIndex(1)
        self.param_section.addWidget(self.mode)
        def update_mode(index):
            if index:
                self.params['mode'] = 'relative'
            else:
                self.params['mode'] = 'excess'
            self.excess_method.dropdown.setEnabled(not index)
            self.ref_channel.dropdown.setEnabled(bool(index))
            self.measure()
            self.plot()
        self.mode.update_callback = update_mode

        # excess phase calculation method dropdown
        self.excess_method = CLParamDropdown('Excess phase method', ['minimum group delay', 'linear phase', 'cross-correlation'])
        if self.params['excess_method'] == 'linear_phase':
            self.excess_method.dropdown.setCurrentIndex(1)
        if self.params['excess_method'] == 'cross_correlation':
            self.excess_method.dropdown.setCurrentIndex(2)
        self.excess_method.dropdown.setEnabled(self.params['mode'] != 'relative')
        self.param_section.addWidget(self.excess_method)
        def update_excess_method(index):
            if index==0:
                self.params['excess_method'] = 'min_delay'
            if index==1:
                self.params['excess_method'] = 'linear_phase'
            if index==2:
                self.params['excess_method'] = 'cross_correlation'
            self.measure()
            self.plot()
        self.excess_method.update_callback = update_excess_method

        # relative phase reference channel dropdown
        self.ref_channel = CLParamDropdown('Loopback reference channel', [''])
        self.ref_channel.dropdown.setEnabled(self.params['mode'] == 'relative')
        self.param_section.addWidget(self.ref_channel)
        def update_ref_channel(index): # todo: still some corner cases that need to be worked out
            self.params['ref_channel'] = int(self.ref_channel.dropdown.currentText())
            
            if self.params['ref_channel'] == clp.project['input']['channel']:
                self.ref_channel.dropdown.setStyleSheet('QComboBox { background-color: orange; }')
            else:
                self.ref_channel.dropdown.setStyleSheet('')

            if self.params['mode'] == 'relative':
                self.measure()
                self.plot()
        self.ref_channel.update_callback = update_ref_channel
        def update_num_channels(num_channels):
            channel_list = [str(chan) for chan in range(1, num_channels+1)]
            # todo: figure out how to build list without reference channel. Introduces a lot of weird state management issues

            self.ref_channel.dropdown.blockSignals(True)
            self.ref_channel.dropdown.clear()
            self.ref_channel.dropdown.addItems(channel_list)
            if self.params['ref_channel'] <= num_channels:
                self.ref_channel.dropdown.setCurrentIndex(channel_list.index(str(self.params['ref_channel'])))
            self.ref_channel.dropdown.blockSignals(False)
            
            if self.params['ref_channel'] <= num_channels:
                update_ref_channel(channel_list.index(str(self.params['ref_channel'])))
            else:
                self.ref_channel.dropdown.setStyleSheet('QComboBox { background-color: orange; }')
        self.update_num_channels = update_num_channels

        # unwrap phase checkbox
        self.unwrap = QCheckBox('Unwrap phase')
        self.unwrap.setChecked(self.params['unwrap'])
        self.param_section.addWidget(self.unwrap)
        def update_unwrap(checked):
            self.params['unwrap'] = checked
            self.measure()
            self.plot()
        self.unwrap.stateChanged.connect(update_unwrap)

        # auto invert checkbox
        self.auto_invert = QCheckBox('Auto invert')
        self.auto_invert.setChecked(self.params['auto_invert'])
        self.param_section.addWidget(self.auto_invert)
        def update_auto_invert(checked):
            self.params['auto_invert'] = checked
            self.measure()
            self.plot()
        self.auto_invert.stateChanged.connect(update_auto_invert)


        self.output_unit = CLParamDropdown('Units', self.OUTPUT_UNITS, '')
        output_unit_index = self.output_unit.dropdown.findText(self.params['output']['unit'])
        if output_unit_index != -1:
            self.output_unit.dropdown.setCurrentIndex(output_unit_index)
        self.output_section.addWidget(self.output_unit)
        def update_output_unit(index):
            self.params['output']['unit'] = self.OUTPUT_UNITS[index]
            self.measure()
            self.plot()
            self.format_graph()
        self.output_unit.update_callback = update_output_unit
        
        self.output_points = FreqPointsParams(self.params['output'])
        self.output_section.addWidget(self.output_points)
        def update_output_points():
            self.measure()
            self.plot()
            self.format_graph()
        self.output_points.update_callback = update_output_points
        self.output_points.calc_min_auto = self.calc_auto_min_freq
        self.output_points.calc_max_auto = self.calc_auto_max_freq
    

    def update_tab(self):
        self.update_num_channels(clp.IO['input']['channels'])
        self.output_points.update_min_max()
        
    def calc_auto_min_freq(self):
        return clp.project['start_freq']
    
    def calc_auto_max_freq(self):
        return min(clp.project['stop_freq'], (clp.project['sample_rate']/2) * 0.9)
