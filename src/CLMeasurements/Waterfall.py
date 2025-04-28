import CLProject as clp
from CLAnalysis import freq_points, interpolate, FS_to_unit
from CLGui import CLParamDropdown, QCollapsible, CLParamNum, FreqPointsParams
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal.windows import hann
import numpy as np
from CLMeasurements import CLMeasurement
import pyqtgraph as pg
#import pyqtgraph.opengl as gl
from CLMeasurements.FrequencyResponse import WindowParamsSection
#from vispy import scene
#from vispy.scene import visuals
# matplotlib stuff at the bottom

# much of the Waterfall measurement is a copy of FrequencyResponse. Much of the calculations and GUI elements are the same or similar, biggest difference is the custom plot() method

# 3D waterfall plotting is done with matplotlib for now, stubs for pyqtgraph and VisPy are here, but both make it very difficult to add axes with ticks, labels, etc.

# helpers to make sample length calculations cleaner, comes up a lot in windowing
def ms_to_samples(ms):
    return round((ms / 1000) * clp.project['sample_rate']) # may need to change round to floor to avoid off-by-one errors
def samples_to_ms(samples):
    return 1000 * samples / clp.project['sample_rate']

class Waterfall(CLMeasurement):
    measurement_type_name = 'Waterfall'
    
    MAX_WINDOW_START = 10 # fixed impulse response window can start up to 10ms before t0
    MAX_WINDOW_END = 1000 # IR window can end up to 1s after t0
    MAX_START_TIME = 1000 # max amount of time before t0 of the first time slice
    MAX_END_TIME = 10000 # max amount of time after t0 of the last time slice
    MAX_SLICES = 1000 # max number of time slices to calculate
    OUTPUT_UNITS = ['dBFS', 'dBSPL', 'dBV', 'FS', 'Pa', 'V']
    
    def __init__(self, name, params=None):
        if params is None:
            params = {}
        super().__init__(name, params)

        if len(params)<3: # populate default measurement parameters if none are provided
            self.params['window_start'] = 5 # for fixed window, amount of time in ms included before beginning of impulse response
            self.params['fade_in'] = 5 # beginning of fixed window ramps up with a half Hann window of width fade_in (must be <= window_start)
            self.params['window_end'] = 10
            self.params['fade_out'] = 1
            self.params['start_time'] =  0 # negative time in ms before t0 to calculate the first time slice. e.g. -10 to start 10ms before t0
            self.params['end_time'] = 10 # time in ms after t0 to calculate the last time slice
            self.params['num_slices'] = 21 # the number of time slices to calculate the waterfall response over. Slice interval = (end_time - start_time) / num_slices
            
            self.params['output'] = { # dict containing parameters for output points, frequency range, resolution, etc.
                'unit': 'dBFS',
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
        # generate array of output frequency points
        self.out_freqs = freq_points(self.params['output']['min_freq'], 
                                     self.params['output']['max_freq'],
                                     self.params['output']['num_points'],
                                     self.params['output']['spacing'],
                                     self.params['output']['round_points'])
        
        # calculate raw impulse response
        ir = ifft(fft(clp.signals['response']) / fft(clp.signals['stimulus']))

        # calculate fft frequencies
        fr_freqs = fftfreq(len(clp.signals['stimulus']), 1/clp.project['sample_rate'])
        # trim to only positive frequencies
        fr_freqs = fr_freqs[1:int(len(fr_freqs)/2)-1] # technically, removes highest point for odd-length inputs, but shouldn't be a problem

        # initialize output data array
        self.out_points = np.zeros([self.params['num_slices'], len(self.out_freqs)])

        def calc_slice_fr(ir, slice_time):
            # convert windowing times to whole samples
            window_start = ms_to_samples(self.params['window_start'])
            fade_in = ms_to_samples(self.params['fade_in'])
            window_end = ms_to_samples(self.params['window_end'])
            fade_out = ms_to_samples(self.params['fade_out'])
            slice_offset = ms_to_samples(slice_time)
            
            # construct window
            window = np.zeros(len(ir))
            window[:fade_in] = hann(fade_in*2)[:fade_in]
            window[fade_in:window_start+window_end-fade_out] = np.ones(window_start-fade_in+window_end-fade_out)
            window[window_start+window_end-fade_out:window_start+window_end] = hann(fade_out*2)[fade_out:]
            window = np.roll(window, -window_start + slice_offset)
            
            # apply window to impulse response
            ir = ir * window
            
            # convert windowed impusle response back to frequency response to use for data output
            fr = fft(ir)
        
            # trim to positive half of spectrum for interpolation
            fr = fr[1:int(len(fr)/2)-1]
            
            # take magnitude of complex frequency response
            fr = np.abs(fr)

            return fr

        # generate array of time slices to analyze
        self.out_times = np.linspace(self.params['start_time'], self.params['end_time'], self.params['num_slices'])

        # loop through time slices
        for i in range(self.params['num_slices']):
            fr = calc_slice_fr(ir, self.out_times[i])
        
            # interpolate output points
            slice_points = interpolate(fr_freqs, fr, self.out_freqs, self.params['output']['spacing']=='linear') # todo: still may not be correct. Verify behavior for linear/log frequency scale *and* linear/log output units
            
            # convert output to desired units
            slice_points = FS_to_unit(slice_points, self.params['output']['unit'])

            # store in output array
            self.out_points[i,:] = slice_points
        
        
        # check for noise sample and calculate noise floor
        if any(clp.signals['noise']):
            noise_ir = ifft(fft(clp.signals['noise']) / fft(clp.signals['stimulus']))
            noise_fr = calc_slice_fr(noise_ir, 0)
            self.out_noise = interpolate(fr_freqs, noise_fr, self.out_freqs, self.params['output']['spacing']=='linear')
            self.out_noise = FS_to_unit(self.out_noise, self.params['output']['unit'])
        else:
            self.out_noise = np.zeros(0)
        
        
    def init_tab(self):
        super().init_tab()

        # plot 3D by default. Need to replace 2D plot with 3D plot
        graph_2D = self.tab.graph

        # matplotlib implementation
        self.tab.graph = MplCanvas()
        self.format_graph()
        
        # pyqtgraph implementation using OpenGL
        #self.tab.graph = gl.GLViewWidget()
        #self.tab.graph.show() # may not be necessary
        
        # VisPy implementation
        #self.canvas = scene.SceneCanvas(keys='interactive', show=True) # the base widget is a "canvas"
        #self.tab.graph = self.canvas.central_widget.add_view() # the main graph that you actually interactive with is a "view"
        #self.tab.graph.camera = 'turntable'
        
        # replace the 2D graph
        graph_2D.parent().layout().replaceWidget(graph_2D, self.tab.graph) # for VisPy replace with `self.canvas.native`
        graph_2D.close()

        
        self.start_time = CLParamNum('First slice time', self.params['start_time'], ['ms','samples'], -self.MAX_START_TIME, 0)
        self.param_section.addWidget(self.start_time)
        def update_start_time(new_val):
            if self.start_time.units.currentIndex():
                self.params['start_time'] = new_val / clp.project['sample_rate']
            else:
                self.params['start_time'] = new_val
            update_slice_period()
            self.measure()
            self.plot()
        self.start_time.update_callback = update_start_time
        def update_start_time_units(index):
            if index:
                self.start_time.set_numtype('int')
                self.start_time.min = -self.MAX_START_TIME * clp.project['sample_rate']
                self.start_time.set_value(ms_to_samples(self.params['start_time']))
            else:
                self.start_time.set_numtype('float')
                self.start_time.min = -self.MAX_START_TIME
                self.start_time.set_value(self.params['start_time'])
        self.start_time.units_update_callback = update_start_time_units
        self.update_start_time_units = update_start_time_units

        self.end_time = CLParamNum('Last slice time', self.params['end_time'], ['ms','samples'], 0, self.MAX_END_TIME)
        self.param_section.addWidget(self.end_time)
        def update_end_time(new_val):
            if self.end_time.units.currentIndex():
                self.params['end_time'] = samples_to_ms(new_val)
            else:
                self.params['end_time'] = new_val
            update_slice_period()
            self.measure()
            self.plot()
        self.end_time.update_callback = update_end_time
        def update_end_time_units(index):
            if index:
                self.end_time.set_numtype('int')
                self.end_time.max = self.MAX_END_TIME * clp.project['sample_rate']
                self.end_time.set_value(ms_to_samples(self.params['end_time']))
            else:
                self.end_time.set_numtype('float')
                self.end_time.max = self.MAX_END_TIME
                self.end_time.set_value(self.params['end_time'])
        self.end_time.units_update_callback = update_end_time_units
        self.update_end_time_units = update_end_time_units

        self.num_slices = CLParamNum('Number of time slices', self.params['num_slices'], None, 1, self.MAX_SLICES, 'int')
        self.param_section.addWidget(self.num_slices)
        def update_num_slices(new_val):
            self.params['num_slices'] = new_val
            update_slice_period()
            self.measure()
            self.plot()
        self.num_slices.update_callback = update_num_slices

        self.slice_period = CLParamNum('Slice time interval', 0, 'ms')
        self.slice_period.setEnabled(False)
        self.param_section.addWidget(self.slice_period)
        def update_slice_period():
            self.slice_period.set_value((self.params['end_time']-self.params['start_time'])/(self.params['num_slices']-1))
        update_slice_period()

        self.window_params = WindowParamsSection(self.params)
        self.param_section.addWidget(self.window_params)
        def update_window_params():
            self.measure()
            self.plot()
        self.window_params.update_callback = update_window_params


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
        self.window_params.update_window_params()
        self.output_points.update_min_max()
        self.update_start_time_units(self.start_time.units.currentIndex())
        self.update_end_time_units(self.end_time.units.currentIndex())
        
    def calc_auto_min_freq(self):
        return clp.project['start_freq']
    
    def calc_auto_max_freq(self):
        return min(clp.project['stop_freq'], (clp.project['sample_rate']/2) * 0.9)

    def plot(self):
        # matplotlib 3D plotting
        for artist in self.tab.graph.axes.collections:
            artist.remove()
        self.tab.graph.axes.set_prop_cycle(None) # todo: default blue color works, but look into a custom color scale

        log_freqs = np.log10(self.out_freqs)
        x, y = np.meshgrid(log_freqs, self.out_times)
        self.tab.graph.axes.plot_surface(x, y, self.out_points)
        self.tab.graph.axes.set_zlabel('Amplitude (' + self.params['output']['unit'] + ')')
        self.tab.graph.draw_idle()
        
        # pyqtgraph 3D plotting
        #self.tab.graph.clear()
        #grid = gl.GLGridItem() # grid defaults to white, invisible with white background unless the grid is between the camera and the actual surface plot
        #self.tab.graph.addItem(grid)
        #axes = gl.GLAxisItem()
        #self.tab.graph.addItem(axes)
        #surf = gl.GLSurfacePlotItem(x=np.log10(self.out_freqs), y=self.out_times, z=self.out_points.transpose(), shader='shaded', color=hex2float(clp.PLOT_COLORS[0]))
        # need to add scaling and translation to get the surface plot in the right spot. Surface is outside of default view, zoom out (mouse scroll wheel) to see it
        #self.tab.graph.addItem(surf)

        # VisPy 3D plotting
        #surface = visuals.SurfacePlot(z=self.out_points, color=hex2float(clp.PLOT_COLORS[0]))
        #self.tab.graph.add(surface)
        #grid = visuals.GridLines(color=(0.5, 0.5, 0.5, 1))
        #self.tab.graph.add(grid)
        

        return
        # todo: consider adding a toggle to select 2D or 3D plotting
        # pyqtgraph 2D plotting with color-coded time slices
        for i in range(self.params['num_slices']):
            if i == 0:
                plot_pen = pg.mkPen(color=clp.PLOT_COLORS[0], width=clp.PLOT_PEN_WIDTH)
                self.tab.graph.plot(self.out_freqs, self.out_points[i, :], name = 't=' + str(self.params['start_time']) + 'ms', pen=plot_pen)
            elif i == (self.params['num_slices'] - 1):
                plot_pen = pg.mkPen(color=clp.PLOT_COLORS[1], width=clp.PLOT_PEN_WIDTH)
                self.tab.graph.plot(self.out_freqs, self.out_points[i, :], name = 't=' + str(self.params['end_time']) + 'ms', pen=plot_pen)
            else:
                slice_color = interp_colors(clp.PLOT_COLORS[0], clp.PLOT_COLORS[1], i/self.params['num_slices'])
                plot_pen = pg.mkPen(color=slice_color, width=clp.PLOT_PEN_WIDTH)
                self.tab.graph.plot(self.out_freqs, self.out_points[i, :], pen=plot_pen)
        
        if clp.project['plot_noise'] and any(self.out_noise):
            noise_pen = pg.mkPen(color=clp.NOISE_COLOR, width=clp.PLOT_PEN_WIDTH)
            self.tab.graph.plot(self.out_freqs, self.out_noise, name='Noise Floor', pen=noise_pen)
            
    def format_graph(self):
        # graph formatting for matplotlib 3D plot
        #self.tab.graph_toolbar = NavigationToolbar(self.tab.graph) # todo: doesn't actually work. Default mouse controls for 3D plots is mostly fine, but it would be nice to be able to pan/zoom a single axis at a time
        self.tab.graph.axes.yaxis.set_inverted(True)
        self.tab.graph.axes.set_title(self.params['name'])
        self.tab.graph.axes.set_xlabel('Frequency (Hz)')
        self.tab.graph.axes.set_ylabel('Time (ms)')
        # #self.tab.graph.axes.set_xscale('log') # log scaling is broken in mpl 3D plots. Need to define a custom tick formatter https://stackoverflow.com/questions/3909794/plotting-mplot3d-axes3d-xyz-surface-plot-with-log-scale
        self.tab.graph.axes.xaxis.set_major_formatter(mticker.FuncFormatter(log_tick_formatter))
        self.tab.graph.axes.xaxis.set_major_locator(mticker.MaxNLocator(integer=True)) # todo: figure out how to plot frequency on a 1-2-5 series
        self.tab.graph.axes.xaxis.set_minor_locator(mticker.MultipleLocator(0.1))
        #self.tab.graph.axes.grid(which='minor', linestyle=':', linewidth=5.0) # todo: this doesn't work for 3D. Figure out how to draw minor gridlines lighter
        self.tab.graph.axes.view_init(elev=15., azim=250)

def interp_colors(color_zero, color_one, ratio):
    # interpolate between two colors
    # Naively mixes RGB values, where ratio=0 returns color_zero and ratio=1 returns color_one, does not take into account hue, saturation, colorspace, etc.
    # colors specified as hex values
    color_zero = color_zero.lstrip('#')
    r0 = int(color_zero[0:2], 16)
    g0 = int(color_zero[2:4], 16)
    b0 = int(color_zero[4:6], 16)

    color_one = color_one.lstrip('#')
    r1 = int(color_one[0:2], 16)
    g1 = int(color_one[2:4], 16)
    b1 = int(color_one[4:6], 16)

    r = round(r0 + ((r1-r0)*ratio))
    g = round(g0 + ((g1-g0)*ratio))
    b = round(b0 + ((b1-b0)*ratio))

    return '#' + hex(r)[2:] + hex(g)[2:] + hex(b)[2:]
        
def hex2float(hex_color, alpha=1.0):
    # convert hex color string to tuple suitable for OpenGl/VisPy with RGB values from 0-1
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255

    return (r, g, b, alpha)



import matplotlib.ticker as mticker
from engineering_notation import EngNumber
def log_tick_formatter(val, pos=None):
    return EngNumber(10**val)

# matplotlib stuff, mostly copied from pythonguis.com
# this was originally in CLTab.py but removed as part of the switch from mpl to pyqtgraph. Maybe put it back in CLTab for other measurements that need a 3D plot
# speed stuff mostly helps when plotting time series signals (like on the ChirpTab), probably doesn't make much of a difference for relatively sparse surface plots
import matplotlib
matplotlib.use('QtAgg') # 'Qt5Agg' is only use for backwards compatibility to force Qt5

#matplotlib speed settings
#matplotlib.style.use('default') # settings are persistent in Spyder. use('default') to reset
# agg.path.chunksize = 0
# path.simplify = True
# path.simplify_threshold = 1/9

#matplotlib.style.use('fast') # fast, but sometimes leaves holes in stimulus/response plots. Equivalent to:
matplotlib.rcParams['agg.path.chunksize'] = 10000
matplotlib.rcParams['path.simplify'] = True
matplotlib.rcParams['path.simplify_threshold'] = 1.0

matplotlib.rcParams["figure.autolayout"] = True # default to tight_layout

# chunksize and simplify_threshold have some interdependency. Increasing one or the other is fine, marginally improves performance. Increasing both improves performance more but introduces artefacts.
#matplotlib.rcParams['agg.path.chunksize'] = 100
#matplotlib.rcParams['path.simplify'] = True
#matplotlib.rcParams['path.simplify_threshold'] = 1.0

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar # todo: test if this breaks compatiblity with other PyQt bindings
from matplotlib.figure import Figure

class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100): # DPI doesn't seem to make artefacts better/worse, Qt or actual display DPI might.
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111, projection='3d')
        super(MplCanvas, self).__init__(fig)
