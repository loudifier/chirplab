import CLProject as clp
from CLAnalysis import freq_points, interpolate
from CLGui import CLParamDropdown, FreqPointsParams
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal.windows import hann
import numpy as np
from CLMeasurements import CLMeasurement
from scipy.stats import linregress

import matplotlib.pyplot as plt # todo: for debugging, remove after initial implementation
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
            self.params['excess_method'] = 'min_delay' # options are 'min_delay' which aligns phase to an estimate of the minimum group delay, 'linear_phase' which aligns to a linear regression of the phase over the chirp, and 'cross_correlation' which uses the time alignment determined by cross correlation when reading the input signal
            self.params['ref_channel'] = 2 # loopback input channel used as the phase reference in 'relative' mode. If there is no input channel ref_channel or ref_channel is the same as the project input channel the measurement will output -1 for all frequency points
            self.params['unwrapped'] = True # if true measurement will attempt to unwrap the phase to be continuous instead of the intermediary calculated values, which are bound to +/-180deg / +/-pi

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

        # calculate raw complex transfer function
        transfer_function = fft(clp.signals['response']) / fft(clp.signals['stimulus'])
        #plt.plot(freqs, np.rad2deg(np.unwrap(np.angle(transfer_function[:round(len(transfer_function)/2)-1]))))
        #plt.show()
        
        # calculate raw impulse response
        impulse_response = ifft(transfer_function)

        # apply an aggressive window to the impulse response. Significantly reduces noise but does not impact low frequency phase accuracy as much as magnitude. Might be overly smooth
        # todo: window width determined empirically, experiment with other widths or exposing as a measurement parameter. Current implementation usually resolves phase at DC to nearest pi to phase at lowest chirp freq
        window_width = round(clp.project['sample_rate'] / clp.project['start_freq'])
        window = np.zeros(len(impulse_response))
        window[:window_width] = hann(window_width)
        window = np.roll(window, -round(window_width/2)) # hann window of width equal to lowest chirp wavelength, centered at t0.
        impulse_response *= window

        # calculate phase from windowed impulse response (and trim to positive frequencies)
        phase = np.rad2deg(np.unwrap(np.angle(fft(impulse_response)[1:round(len(transfer_function)/2)])))

        # calculate group delay from phase
        delay = -(np.roll(phase,-1)-np.roll(phase,1))/(360*freqs[1])

        # find the minimum and maximum bins that cover the frequency range of the chirp
        min_bin = np.argmin(np.abs(freqs - clp.project['start_freq'])) + 1
        max_bin = np.argmin(np.abs(freqs - clp.project['stop_freq'])) - 1

        # get group delay on a log frequency scale (otherwise min calculation will be overly influenced by noisy high frequencies)
        log_freqs = freq_points(freqs[min_bin], freqs[max_bin], round(96*np.log2(clp.project['stop_freq']/clp.project['start_freq']))) # 96 points per octave
        log_delay = interpolate(freqs, delay, log_freqs)

        # get an estimate of the minimum group delay
        #min_delay = np.percentile(delay[min_bin:max_bin],10) # 10th percentile helps reject noisy spikes that are not fully smoothed by IR windowing, also still reasonably acccurate for most electrical/purely digital measurements where minimum delay is at max frequency
        min_delay = np.percentile(log_delay,10)

        # remove effective minimum group delay from initial phase calculation
        phase = phase + min_delay * freqs * 360

        # generate array of output frequency points
        self.out_freqs = freq_points(self.params['output']['min_freq'], 
                                     self.params['output']['max_freq'],
                                     self.params['output']['num_points'],
                                     self.params['output']['spacing'],
                                     self.params['output']['round_points'])
        
        # interpolate output points
        self.out_points = interpolate(freqs, phase, self.out_freqs, self.params['output']['spacing']=='linear')
        
        # convert output to desired units
        if self.params['output']['unit'] == 'rad':
            self.out_points = np.deg2rad(self.out_points)
        
        
        
    def init_tab(self):
        super().init_tab()


        self.output_unit = CLParamDropdown('Units', [unit for unit in self.OUTPUT_UNITS], '')
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
        self.output_points.update_min_max()
        
    def calc_auto_min_freq(self):
        return clp.project['start_freq']
    
    def calc_auto_max_freq(self):
        return min(clp.project['stop_freq'], (clp.project['sample_rate']/2) * 0.9)
