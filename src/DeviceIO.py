import pyaudio
import CLProject as clp
import numpy as np
import sys

pa = pyaudio.PyAudio()

# List of host APIs that are supported. By default only make use of MME and WASAPI
if sys.platform == 'win32':
    # MME is the highest-level Windows audio API, the one used by most programs that don't need to know or care about the actual hardware being used. Limited to 2 channels, worst-case latency, automatic resampling, volume control can't be bypassed, etc.
    # WASAPI is the base audio API on Windows. All audio on Windows goes through WASAPI (except for stuff like ASIO that specifically bypasses WASAPI). Channels, sammple rates, and formats are RAW, no resampling. Latency can be competitive with ASIO (but it depends on a lot of factors)
    # DirectSound and WDM are older APIs. DirectSound provides high level resampling and other convenience features, primarily for DirectX games. I believe it still has unique use-cases for games and media apps, but none which are particularly relevant to audio measurements. WDM used to provide direct access to devices for low latency. Now they DirectSound and WDM go through WASAPI for backwards compatibility with older software targeting those APIs
    HOST_APIS = ['MME', 'Windows WASAPI']
elif 'linux' in sys.platform:
    # ALSA is the base auio API for most Linux distros, similar to WASAPI but with feature bloat over the years
    # JACK is an audio processing server in the traditional Linux modular server-client model. It started as a compatibility layer to overcome some of the limitations of ALSA and has grown to be the de facto standard audio interface for serious audio in Linux. PipeAudio is theoretically backwards compatible with JACK, but documentation and examples are hard to find
    HOST_APIS = ['ALSA']
    if 'JACK' in get_api_names(): # todo: actually test this on a machine with Jack installed
        HOST_APIS += ['JACK']
else:
    # Core Audio is the Mac audio API. Thinner and more expensive than other APIs. Incompatible with headphone jacks.
    HOST_APIS = ['Core Audio']

def restart_pyaudio():
    global pa
    pa.terminate()
    pa = pyaudio.PyAudio()

def win2utf8(win_str):
    # convert mangled text incorrectly decoded as Windows-1252 to utf-8
    # handles '®' symbol in device names, probably also '™' and similar symbols
    # https://www.i18nqa.com/debug/utf8-debug.html
    return(bytearray(win_str, 'cp1252').decode('utf-8'))

def get_api_names():
    num_apis = pa.get_host_api_count()
    api_names = []
    for i in range(num_apis):
        api = pa.get_host_api_info_by_index(i)
        api_names.append(api['name'])
    return api_names

def api_name_to_index(name):
    api_names = get_api_names()
    return api_names.index(name)

def get_device_names(input_or_output='', api=''):
    apis = get_api_names()
    num_devices = pa.get_device_count()
    devices = []
    for i in range(num_devices):
        device = pa.get_device_info_by_index(i)
        if api and api != apis[device['hostApi']]:
            continue # skip device if API is specified and device uses a different API
        if input_or_output=='input' and not device['maxInputChannels']:
            continue # skip device if input is specified and device does not have any input channels
        if input_or_output=='output' and not device['maxOutputChannels']:
            continue # skip device if input is specified and device does not have any input channels
        devices.append(win2utf8(device['name']))
    return devices

def device_name_to_index(device_name, api_name=''): # API needs to be specified because it is very likely for a device to have the same name for multiple APIs
    if not api_name:
        api_name = HOST_APIS[0]
    api_index = api_name_to_index(api_name)

    num_devices = pa.get_device_count()
    for i in range(num_devices):
        device = pa.get_device_info_by_index(i)
        if device['hostApi']==api_index and win2utf8(device['name'])==device_name:
            return i
        
def get_default_input_device(api_name=''):
    if not api_name:
        return(win2utf8(pa.get_default_input_device_info()['name']))
    device_index = pa.get_host_api_info_by_index(api_name_to_index(api_name))['defaultInputDevice']
    return(win2utf8(pa.get_device_info_by_index(device_index)['name']))

def get_default_output_device(api_name=''):
    if not api_name:
        return(win2utf8(pa.get_default_output_device_info()['name']))
    device_index = pa.get_host_api_info_by_index(api_name_to_index(api_name))['defaultOutputDevice']
    return(win2utf8(pa.get_device_info_by_index(device_index)['name']))

def is_sample_rate_valid(sample_rate, device_name, api_name):
    device_index = device_name_to_index(device_name, api_name)
    device = pa.get_device_info_by_index(device_index)
    if device['maxInputChannels'] > device['maxOutputChannels']: # theoretically, devices with both input and output channels support the same sample rates for input and output
        # input device
        try:
            return pa.is_format_supported(rate=sample_rate, input_device=device_index, input_channels=device['maxInputChannels'], input_format=pyaudio.paFloat32)
        except ValueError:
            return False
    else:
        # output device
        try:
            return pa.is_format_supported(rate=sample_rate, output_device=device_index, output_channels=device['maxOutputChannels'], output_format=pyaudio.paFloat32)
        except ValueError:
            return False

def get_valid_standard_sample_rates(device_name, api_name):
    valid_rates = []
    for rate in clp.STANDARD_SAMPLE_RATES:
        if is_sample_rate_valid(rate, device_name, api_name):
            valid_rates.append(rate)
    return valid_rates

def get_num_input_channels(device_name, api_name):
    device_index = device_name_to_index(device_name, api_name)
    device = pa.get_device_info_by_index(device_index)
    return device['maxInputChannels']

def get_num_output_channels(device_name, api_name):
    device_index = device_name_to_index(device_name, api_name)
    device = pa.get_device_info_by_index(device_index)
    return device['maxOutputChannels']

def play(out_signal, sample_rate, device_name, api_name, active_callback=None, finished_callback=None):
    # assumes width of out_signal equals the number of output channels to play back
    device_index = device_name_to_index(device_name, api_name)
    num_channels = out_signal.shape[1]
    
    out_signal = out_signal.astype(np.float32)
    out_signal = out_signal.ravel()

    chunk_count = 0
    last_chunk = False
    def play_callback(in_data, frame_count, time_info, status):
        nonlocal chunk_count
        data = out_signal[chunk_count*frame_count*num_channels:chunk_count*frame_count*num_channels+frame_count*num_channels]
        chunk_count += 1

        nonlocal last_chunk
        if last_chunk:
            if finished_callback is not None:
                finished_callback()
            return (data, pyaudio.paComplete)

        if len(data)<(frame_count*num_channels):
            # pad last frame so the play callback will be called one last time
            data = np.append(data, np.zeros(frame_count*num_channels - len(data)))
            last_chunk = True

        if active_callback is not None:
            active_callback()

        return (data, pyaudio.paContinue)

    stream = pa.open(rate=sample_rate, channels=num_channels, format=pyaudio.paFloat32, output=True, output_device_index=device_index, stream_callback=play_callback)

def record(record_length_samples, sample_rate, device_name, api_name, active_callback=None, finished_callback=None):
    device_index = device_name_to_index(device_name, api_name)
    num_channels = pa.get_device_info_by_index(device_index)['maxInputChannels']
    
    record_frames = []

    def record_callback(in_data, frame_count, time_info, status):
        if len(record_frames)*frame_count < record_length_samples:
            record_frames.append(np.frombuffer(in_data, dtype=np.float32)) # todo: append() in a loop is usually a faux pas. Run some experiments with pre-allocating and/or doing things directly with numpy instead of lists

            if active_callback is not None:
                active_callback()
            
            return (None, pyaudio.paContinue)
        
        else:
            if finished_callback is not None:
                finished_callback(np.hstack(record_frames).reshape(-1 , num_channels)) # is there a more direct way to asynchronously output data? Returning record_frames ends the recording early and waiting for the recording to finish blocks GUI thread
            return (None, pyaudio.paComplete)

    stream = pa.open(rate=sample_rate, channels=num_channels, format=pyaudio.paFloat32, input=True, input_device_index=device_index, stream_callback=record_callback)


# run directly to print out APIs and devices for debugging purposes
if __name__ == '__main__':
    num_apis = pa.get_host_api_count()
    api_names = []
    for i in range(num_apis):
        print(pa.get_host_api_info_by_index(i))

    print('')

    num_devices = pa.get_device_count()
    for i in range(num_devices):
        print(pa.get_device_info_by_index(i))