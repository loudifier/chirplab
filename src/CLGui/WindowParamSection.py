import CLProject as clp
from CLAnalysis import samples_to_ms, ms_to_samples
from CLGui import QCollapsible, CLParamNum
from CLMeasurements import FrequencyResponse

# break out fixed windowing parameters UI elements, so they can be reused in the impulse response visualizer dialog
# also try to contain some of the spaghetti that is generated when updating one window parameter cascades to updating other parameters
# params should be a reference to the measurement's params or another dict that includes 'window_start', 'fade_in', 'window_end', and 'fade_out' times in ms
class WindowParamsSection(QCollapsible):
    def __init__(self, params):
        super().__init__('Window settings')
        
        self.update_callback = None
        
        # maximum length of each window feature changes dynamically based on the other features and total impulse response length
        # helpers to calculate the max length of each feature (in ms)
        def max_window_start():
            # hard limit, or total impulse response length minus the current window end
            return min(FrequencyResponse.MAX_WINDOW_START, samples_to_ms(len(clp.signals['stimulus'])) - params['window_end'])
        # max fade in is limited to the current window start length
        def max_window_end():
            # hard limit, or total impulse response length
            return min(FrequencyResponse.MAX_WINDOW_END, samples_to_ms(len(clp.signals['stimulus'])))
        # max fade out is limited to the current window end length
        
        
        self.window_start = CLParamNum('Window start', params['window_start'], ['ms', 'samples'], 0, max_window_start(), 'float')
        self.addWidget(self.window_start)
        def update_window_start(new_value):
            # update param with new value, even if it is invalid, then clean up all window parameters together
            if self.window_start.units.currentIndex():
                params['window_start'] = samples_to_ms(new_value)
            else:
                params['window_start'] = new_value
            update_window_params()
            if self.update_callback:
                self.update_callback()
        self.window_start.update_callback = update_window_start
        def update_window_start_units(index):
            if index: # samples
                self.window_start.set_numtype('int')
                self.window_start.max = ms_to_samples(max_window_start())
                self.window_start.set_value(ms_to_samples(params['window_start']))
            else: # ms
                self.window_start.set_numtype('float')
                self.window_start.max = max_window_start()
                self.window_start.set_value(params['window_start'])
        self.window_start.units_update_callback = update_window_start_units

        self.fade_in = CLParamNum('Fade in', params['fade_in'], ['ms', 'samples'], 0, params['window_start'], 'float')
        self.addWidget(self.fade_in)
        def update_fade_in(new_value):
            if self.fade_in.units.currentIndex():
                params['fade_in'] = samples_to_ms(new_value)
            else:
                params['fade_in'] = new_value
            update_window_params()
            if self.update_callback:
                self.update_callback()
        self.fade_in.update_callback = update_fade_in
        def update_fade_in_units(index):
            if index: # samples
                self.fade_in.set_numtype('int')
                self.fade_in.max = ms_to_samples(params['window_start'])
                self.fade_in.set_value(ms_to_samples(params['fade_in']))
            else: # ms
                self.fade_in.set_numtype('float')
                self.fade_in.max = params['window_start']
                self.fade_in.set_value(params['fade_in'])
        self.fade_in.units_update_callback = update_fade_in_units
        
        self.window_end = CLParamNum('Window end', params['window_end'], ['ms', 'samples'], 0, max_window_end(), 'float')
        self.addWidget(self.window_end)
        def update_window_end(new_value):
            if self.window_end.units.currentIndex():
                params['window_end'] = samples_to_ms(new_value)
            else:
                params['window_end'] = new_value
            update_window_params()
            if self.update_callback:
                self.update_callback()
        self.window_end.update_callback = update_window_end
        def update_window_end_units(index):
            if index: # samples
                self.window_end.set_numtype('int')
                self.window_end.max = ms_to_samples(max_window_end())
                self.window_end.set_value(ms_to_samples(params['window_end']))
            else: # ms
                self.window_end.set_numtype('float')
                self.window_end.max = max_window_end()
                self.window_end.set_value(params['window_end'])
        self.window_end.units_update_callback = update_window_end_units
        
        self.fade_out = CLParamNum('Fade out', params['fade_out'], ['ms', 'samples'], 0, params['window_end'], 'float')
        self.addWidget(self.fade_out)
        def update_fade_out(new_value):
            if self.fade_out.units.currentIndex():
                params['fade_out'] = samples_to_ms(new_value)
            else:
                params['fade_out'] = new_value
            update_window_params()
            if self.update_callback:
                self.update_callback()
        self.fade_out.update_callback = update_fade_out
        def update_fade_out_units(index):
            if index: # samples
                self.fade_out.set_numtype('int')
                self.fade_out.max = ms_to_samples(params['window_end'])
                self.fade_out.set_value(ms_to_samples(params['fade_out']))
            else: # ms
                self.fade_out.set_numtype('float')
                self.fade_out.max = params['window_end']
                self.fade_out.set_value(params['fade_out'])
        self.fade_out.units_update_callback = update_fade_out_units
        
        def update_window_params():
            # window parameter lengths propogate in the order of:
            #   window_end
            #   --> fade_out
            #   --> window_start
            #       --> fade_in
            params['window_end'] = min(params['window_end'], max_window_end())
            params['fade_out'] = min(params['fade_out'], params['window_end'])
            params['window_start'] = min(params['window_start'], max_window_start())
            params['fade_in'] = min(params['fade_in'], params['window_start'])
            
            update_window_end_units(self.window_end.units.currentIndex())
            update_fade_out_units(self.fade_out.units.currentIndex())
            update_window_start_units(self.window_start.units.currentIndex())
            update_fade_in_units(self.fade_in.units.currentIndex())
        self.update_window_params = update_window_params # promote inner function to method