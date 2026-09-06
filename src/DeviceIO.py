import os
os.environ['SD_ENABLE_ASIO'] = '1'
import sounddevice as sd
import CLProject as clp
import numpy as np
import sys

def get_api_names():
    return [api['name'] for api in sd.query_hostapis()]

# List of host APIs that are supported. By default only make use of MME and WASAPI
if sys.platform == 'win32':
    # MME is the highest-level Windows audio API, the one used by most programs that don't need to know or care about the actual hardware being used. Limited to 2 channels, worst-case latency, automatic resampling, volume control can't be bypassed, etc.
    # WASAPI is the base audio API on Windows. All audio on Windows goes through WASAPI (except for stuff like ASIO that specifically bypasses WASAPI). Channels, sammple rates, and formats are RAW, no resampling. Latency can be competitive with ASIO (but it depends on a lot of factors)
    # DirectSound and WDM are older APIs. DirectSound provides high level resampling and other convenience features, primarily for DirectX games. I believe it still has unique use-cases for games and media apps, but none which are particularly relevant to audio measurements. WDM used to provide direct access to devices for low latency. Now DirectSound and WDM go through WASAPI for backwards compatibility with older software targeting those APIs
    # ASIO is a proprietary protocol from Steinberg, which has been open sourced under the GPL. It completely bypasses WASAPI and the standard Windows APIs, and generally provides more control and lower latency for pro audio interfaces.
    HOST_APIS = ['MME', 'Windows WASAPI', 'ASIO']
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

def win2utf8(win_str): # todo: this is an issue with PyAudio, check if sounddevice already handles it
    # convert mangled text incorrectly decoded as Windows-1252 to utf-8
    # handles '®' symbol in device names, probably also '™' and similar symbols
    # https://www.i18nqa.com/debug/utf8-debug.html
    return(bytearray(win_str, 'cp1252').decode('utf-8'))

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
        devices.append(win2utf8(device['name']))
    return devices

def device_name_to_index(device_name, api_name=''): # API needs to be specified because it is very likely for a device to have the same name for multiple APIs
    if not api_name:
        api_name = HOST_APIS[0]
    api_index = api_name_to_index(api_name)

    num_devices = len(sd.query_devices())
    for i in range(num_devices):
        device = sd.query_devices(i)
        if device['hostapi']==api_index and win2utf8(device['name'])==device_name:
            return i
        
def get_default_input_device(api_name=''):
    if not api_name:
        return(win2utf8(sd.query_devices(sd.default.device[0])['name']))
    device_index = sd.query_hostapis(api_name_to_index(api_name))['default_input_device']
    return(win2utf8(sd.query_devices(device_index)['name']))

def get_default_output_device(api_name=''):
    if not api_name:
        return(win2utf8(sd.query_devices(sd.default.device[1])['name']))
    device_index = sd.query_hostapis(api_name_to_index(api_name))['default_output_device']
    return(win2utf8(sd.query_devices(device_index)['name']))

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

        if (play_position + frames) < len(out_signal):
            outdata[:] = out_signal[play_position:play_position + frames, :]
            play_position += frames

            if active_callback is not None:
                active_callback()

        else:
            outdata[:] = np.vstack((out_signal[play_position:], np.zeros((frames - (len(out_signal) - play_position), num_channels)).astype(np.float32)))

            raise sd.CallbackStop()
        

    stream = sd.OutputStream(samplerate=sample_rate, device=device_index, channels=num_channels, callback=play_callback, finished_callback=finished_callback)
    stream.start()

def record(record_length_samples, sample_rate, device_name, api_name, active_callback=None, finished_callback=None):
    device_index = device_name_to_index(device_name, api_name)
    num_channels = get_num_input_channels(device_name, api_name)
    
    record_frames = np.zeros((record_length_samples, num_channels))
    record_position = 0

    def record_callback(indata, frames, time, status):
        nonlocal record_position

        if (record_position + frames) < record_length_samples:
            record_frames[record_position:record_position + frames] = indata
            record_position += frames
            
            if active_callback is not None:
                active_callback()
        
        else:
            record_frames[record_position:] = indata[:record_length_samples - record_position]

            if finished_callback is not None:
                finished_callback(record_frames)

            raise sd.CallbackStop()

    stream = sd.InputStream(samplerate=sample_rate, device=device_index, channels=num_channels, callback=record_callback)
    stream.start()

def stream_input(sample_rate, device_name, api_name, stream_callback, samples_per_chunk=None):
    device_index = device_name_to_index(device_name, api_name)
    num_channels = pa.get_device_info_by_index(device_index)['maxInputChannels']

    def callback(in_data, frame_count, time_info, status):
        stream_callback(np.frombuffer(in_data, dtype=np.float32).reshape(-1, num_channels))
        return (None, pyaudio.paContinue)

    # return handle to stream object. Will continue streaming to callback indefinitely until <stream>.close_stream() is called
    if samples_per_chunk is None:
        return pa.open(rate=sample_rate, channels=num_channels, format=pyaudio.paFloat32, input=True, input_device_index=device_index, stream_callback=callback)
    else:
        return pa.open(rate=sample_rate, channels=num_channels, format=pyaudio.paFloat32, input=True, input_device_index=device_index, stream_callback=callback, frames_per_buffer=samples_per_chunk)
