import os
os.environ['SD_ENABLE_ASIO'] = '1'
import sounddevice as sd
import CLProject as clp
import numpy as np
import sys
from qtpy.QtCore import Signal, Slot, QObject

def get_api_names():
    return [api['name'] for api in sd.query_hostapis()]

# List of host APIs that are supported. By default only make use of MME and WASAPI
if sys.platform == 'win32':
    # MME is the highest-level Windows audio API, the one used by most programs that don't need to know or care about the actual hardware being used. Limited to 2 channels, worst-case latency, automatic resampling, volume control can't be bypassed, etc.
    # WASAPI is the base audio API on Windows. All audio on Windows goes through WASAPI (except for stuff like ASIO that specifically bypasses WASAPI). Channels, sammple rates, and formats are RAW, no resampling. Latency can be competitive with ASIO (but it depends on a lot of factors)
    # DirectSound and WDM are older APIs. DirectSound provides high level resampling and other convenience features, primarily for DirectX games. I believe it still has unique use-cases for games and media apps, but none which are particularly relevant to audio measurements. WDM used to provide direct access to devices for low latency. Now DirectSound and WDM go through WASAPI for backwards compatibility with older software targeting those APIs
    # ASIO is a proprietary protocol from Steinberg, which has been open sourced under the GPL. It completely bypasses WASAPI and the standard Windows APIs, and generally provides more control and lower latency for pro audio interfaces.
    HOST_APIS = ['MME', 'Windows WASAPI']
    if any([hostapi['devices'] for hostapi in sd.query_hostapis() if hostapi['name']=='ASIO']):
        HOST_APIS += ['ASIO']
elif 'linux' in sys.platform:
    # ALSA is the base auio API for most Linux distros, similar to WASAPI but with feature bloat over the years. Instead use JACK if at all possible
    # JACK is an audio processing server in the traditional Linux modular server-client model. It started as a compatibility layer to overcome some of the limitations of ALSA and has grown to be the de facto standard audio interface for serious audio in Linux. PipeAudio is theoretically backwards compatible with JACK, but documentation and examples are hard to find
    HOST_APIS = ['ALSA']
    if 'JACK Audio Connection Kit' in get_api_names(): # todo: actually test this on a machine with Jack installed
        HOST_APIS += ['JACK Audio Connection Kit']
else:
    # Core Audio is the Mac audio API. Thinner and more expensive than other APIs. Incompatible with headphone jacks.
    HOST_APIS = ['Core Audio']

def refresh_device_list():
    sd._terminate()
    sd._initialize()

def api_name_to_index(name):
    api_names = get_api_names()
    return api_names.index(name)

def get_device_names(input_or_output='', api=''):
    apis = get_api_names()
    num_devices = len(sd.query_devices())
    devices = []
    for i in range(num_devices):
        device = sd.query_devices(i)
        if api and api != apis[device['hostapi']]:
            continue # skip device if API is specified and device uses a different API
        if input_or_output=='input' and not device['max_input_channels']:
            continue # skip device if input is specified and device does not have any input channels
        if input_or_output=='output' and not device['max_output_channels']:
            continue # skip device if input is specified and device does not have any input channels
        devices.append(device['name'])
    return devices

def device_name_to_index(device_name, api_name=''): # API needs to be specified because it is very likely for a device to have the same name for multiple APIs
    if not api_name:
        api_name = HOST_APIS[0]
    api_index = api_name_to_index(api_name)

    num_devices = len(sd.query_devices())
    for i in range(num_devices):
        device = sd.query_devices(i)
        if device['hostapi']==api_index and device['name']==device_name:
            return i
        
def get_default_input_device(api_name=''):
    if not api_name:
        return(sd.query_devices(sd.default.device[0])['name'])
    device_index = sd.query_hostapis(api_name_to_index(api_name))['default_input_device']
    return(sd.query_devices(device_index)['name'])

def get_default_output_device(api_name=''):
    if not api_name:
        return(sd.query_devices(sd.default.device[1])['name'])
    device_index = sd.query_hostapis(api_name_to_index(api_name))['default_output_device']
    return(sd.query_devices(device_index)['name'])

def is_sample_rate_valid(sample_rate, device_name, api_name):
    device_index = device_name_to_index(device_name, api_name)
    device = sd.query_devices(device_index)
    if device['max_input_channels'] > device['max_output_channels']: # theoretically, devices with both input and output channels support the same sample rates for input and output
        # input device
        try:
            return sd.check_input_settings(device=device_index, channels=device['max_input_channels'], samplerate=sample_rate) is None
        except sd.PortAudioError:
            return False
    else:
        # output device
        try:
            return sd.check_output_settings(device=device_index, channels=device['max_output_channels'], samplerate=sample_rate) is None
        except sd.PortAudioError:
            return False
    

def get_valid_standard_sample_rates(device_name, api_name):
    valid_rates = []
    for rate in clp.STANDARD_SAMPLE_RATES:
        if is_sample_rate_valid(rate, device_name, api_name):
            valid_rates.append(rate)
    return valid_rates

def get_num_input_channels(device_name, api_name):
    device_index = device_name_to_index(device_name, api_name)
    device = sd.query_devices(device_index)
    return device['max_input_channels']

def get_num_output_channels(device_name, api_name):
    device_index = device_name_to_index(device_name, api_name)
    device = sd.query_devices(device_index)
    return device['max_output_channels']

def play(out_signal, sample_rate, device_name, api_name, active_callback=None, finished_callback=None):
    # assumes width of out_signal equals the number of output channels to play back
    device_index = device_name_to_index(device_name, api_name)
    num_channels = out_signal.shape[1]
    
    out_signal = out_signal.astype(np.float32)

    play_position = 0
    def play_callback(outdata, frames, time, status):
        nonlocal play_position
        nonlocal stream

        if play_position < len(out_signal):
        
            if (play_position + frames) < len(out_signal):
                outdata[:] = out_signal[play_position:play_position + frames, :]
            else:
                outdata[:] = np.vstack((out_signal[play_position:], np.zeros((frames - (len(out_signal) - play_position), num_channels)).astype(np.float32)))
                
            if active_callback is not None:
                active_callback()

        else:
            outdata[:] = np.zeros((frames, num_channels), dtype=np.float32)
            
            if play_position > len(out_signal) + 2*frames: # make sure at least one full frame of silence has been played before completely closing stream
                if finished_callback is not None:
                    finished_callback(stream)

                raise sd.CallbackAbort()

        play_position += frames

    stream = sd.OutputStream(samplerate=sample_rate, device=device_index, channels=num_channels, callback=play_callback)
    stream.start()

def record(record_length_samples, sample_rate, device_name, api_name, active_callback=None, finished_callback=None, frame_size=None):
    def record_callback(record_data):
        if active_callback is not None:
            active_callback(record_data)

        if stream.total_input_samples > (record_length_samples + len(record_data)): # stream.stop() can cut end off recording, let the input stream capture at least one full frame past the record length
            stream.stop() # stream sends full recording to finished_callback

    stream = InputStream(sample_rate, device_name, api_name, record_callback, start=True, frame_size=frame_size, record_length_samples=record_length_samples, finished_callback=finished_callback)

class InputStream:
    # signal/slot mechanism to transfer device input data from audio thread to Qt thread
    class StreamReceiver(QObject):
        frame_received = Signal(np.ndarray)
        def __init__(self, receive_callback):
            super().__init__()
            self.frame_received.connect(receive_callback)

    def __init__(self, sample_rate, device_name, api_name, active_callback=None, finished_callback=None, start=False, frame_size=None, record_length_samples=0):
        self.active_callback = active_callback
        self.finished_callback = finished_callback

        self.total_input_samples = 0

        device_index = device_name_to_index(device_name, api_name)
        num_channels = get_num_input_channels(device_name, api_name)

        @Slot(np.ndarray)
        def receive_frame(frame_samples):
            if self.active_callback is not None:
                self.active_callback(frame_samples)

        self.stream_receiver = self.StreamReceiver(receive_frame)

        self.record_indata = np.zeros((record_length_samples,num_channels)) # recording inside audio thread is more reliable than transferring frames to Qt thread

        def stream_callback(indata, frames, time, status):
            if record_length_samples:
                if self.total_input_samples < record_length_samples:
                    if self.total_input_samples + frames < record_length_samples:
                        self.record_indata[self.total_input_samples:self.total_input_samples+frames] = indata
                    else:
                        self.record_indata[self.total_input_samples:] = indata[:record_length_samples-self.total_input_samples]

            self.total_input_samples += frames
            self.stream_receiver.frame_received.emit(indata) # send frame to Qt thread
            
        self.stream = sd.InputStream(samplerate=sample_rate, device=device_index, channels=num_channels, callback=stream_callback, blocksize=frame_size)
        if start:
            self.stream.start()

    def start(self):
        self.stream.start()

    def stop(self):
        self.stream.stop()

        if self.finished_callback is not None:
            self.finished_callback(self.record_indata)
