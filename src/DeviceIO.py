import pyaudio
import CLProject as clp
import numpy as np
from time import sleep
import matplotlib.pyplot as plt

# List of host APIs that are supported. By default only make use of MME and WASAPI
# MME is the highest-level API, the one used by 99% of programs that don't need to know or care about the actual hardware being used. Limited to 2 channels, worst-case latency, automatic resampling, volume control can't be bypassed, etc.
# WASAPI is the base audio API on Windows. All audio on Windows goes through WASAPI (except for stuff like ASIO that specifically bypasses WASAPI). Channels, sammple rates, and formats are RAW, no resampling. Latency can be competitive with ASIO (but it depends on a lot of factors)
# DirectSound and WDM are older APIs. DirectSound provided high level resampling and other convenience features and WDM used to provide direct access to devices for low latency. Now they both go through WASAPI and exist mostly for backwards compatibility with older software targeting those APIs
HOST_APIS = ['MME', 'Windows WASAPI'] # todo: update to use standard APIs on Linux/Mac

pa = pyaudio.PyAudio() # if you can't open multiple streams with separate APIs, I think you can create a separate instance 

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

capture_frames = []
def capture_callback(in_data, frame_count, time_info, status):
    capture_frames.append(np.frombuffer(in_data, dtype=np.int16))
    return (None, pyaudio.paContinue)
#in_stream = pa.open(rate=48000, channels=1, format=pyaudio.paInt16, input=True, input_device_index=1, stream_callback=capture_callback)

#play_data = np.array(logchirp(100, 20000, 1.0, 48000) * 1, dtype=np.float32)
chunk_count = 0

def play_callback(in_data, frame_count, time_info, status):
    global chunk_count
    #out_data = play_data[chunk_count*frame_count:chunk_count*frame_count+frame_count]
    #chunk_count += 1
    #return (out_data, pyaudio.paContinue)
    
    #return (play_data, pyaudio.paContinue)
#out_stream = pa.open(rate=48000, channels=1, format=pyaudio.paFloat32, output=True, output_device_index=8, stream_callback=play_callback)#, frames_per_buffer=len(play_data))

#sleep(5)
#in_stream.close()
#out_stream.close()

#plt.plot(np.hstack(capture_frames))
#plt.show()
