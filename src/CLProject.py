# module for sharing globals throughout chirplab

from pathlib import Path

import sys
IS_BUNDLED = (getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')) # true if Chirplab is being run via pyinstaller bundle

# project dictionary containing parameters of log chirp used for signal generation and analysis, signal input and output, etc
project = {}

project_file = '' # full path to the project file
working_directory = '.' # directory to start any browse dialogs in, updated based on last GUI browse result

# signals updated from chirp tab and used for analysis in measurements. Stimulus, response, impulse response, etc.
signals = {}

# information to keep track of input and output file or device. For now only keeping track of input file or device information, project output parameters are sufficient for outputting to files or sound cards. May need to use IO['output'] at some point if outputting to some other interface.
IO = {'input':{'length_samples':0,
               'sample_rate':0,
               'channels':0,
               'numtype':''},
      'output':{}}

# list of measurement objects (to be defined and instantiated based on measurement parameters in project dict)
measurements = []

# global variable to check if Chirplab is running in CLI mode or GUI mode
gui_mode = False

# external references
# should probably be loaded from global config file, handled differently in compiled exe
bin_dir = str(Path(__file__).parent) + '/bin/' # external binaries called at runtime
sox_path = bin_dir + 'sox-14.4.2/sox.exe'
sox_dl_url = 'https://sourceforge.net/projects/sox/files/sox/14.4.2/sox-14.4.2-win32.zip/download'


# when loading project files from older versions of chirplab, the project may be able to be upgraded for compatibility with current version
CHIRPLAB_VERSION = 0.3


# constants
MIN_CHIRP_LENGTH = 0.1 # min/max chirp length in seconds
MAX_CHIRP_LENGTH = 60
MIN_CHIRP_FREQ = 0.01
MAX_ZERO_PAD = 10.0 # max length pre/post sweep length in seconds
STANDARD_SAMPLE_RATES = [8000, 16000, 44100, 48000, 96000, 192000]
MIN_SAMPLE_RATE = 1000
MAX_SAMPLE_RATE = 768000
OUTPUT_BIT_DEPTHS = ['16 int', '24 int', '32 int', '32 float']
MAX_OUTPUT_CHANNELS = 16


# GUI style parameters
GRAPH_BG = 'w'
GRAPH_FG = 'k'
PLOT_COLORS = [ # default color order used by MATLAB
    '#0072BD', # blue
    '#D95319', # orange
    '#EDB120', # yellow
    '#7E2F8E', # purple
    '#77AC30', # green
    '#4DBEEE', # light blue
    '#A2142F'] # red
NOISE_COLOR = '#808080'
PLOT_PEN_WIDTH = 3 # some high density plots force the pen width to 1, which is much faster


# default project parameters
if IS_BUNDLED: # todo: rethink how the new project response file is included with bundled app.
    newproj_response_dir = './examples/'
else:
    newproj_response_dir = '../examples/'

def new_project():
    global project_file
    project_file = 'New Project'

    global working_directory
    working_directory = str(Path(__file__).parent)
    
    global project
    project = {
        'chirplab_version': CHIRPLAB_VERSION,
        
        # chirp parameters
        'start_freq': 100, # chirp starting frequency in Hz
        'stop_freq': 20000,
        'chirp_length': 1.0, # length in seconds
        
        # chirp analysis parameters
        'pre_sweep': 0.05, # silence before start of chirp included in analysis window, length in seconds
        'post_sweep': 0.05,
        'sample_rate': 48000, # sample rate in Hz used for all analysis
        'use_input_rate': True, # get the sample rate of the input file or device and update sample_rate before performing and calculations
        
        # calibration parameters
        'FS_per_Pa': 1.0, # acoustic input level in Full Scale units per Pascal. e.g. for a 94dBSPL sensitivity of -37dBFS, FS_per_Pa = 0.0141
        'FS_per_V': 1.0, # electrical input level in Full Scale units per Volt. e.g for a full scale input voltage of +16dBu, FS_per_V = 0.2045
        # for an analog mic with -40dBV sensitivity and interface with +16dBu full scale input voltage (EMM-6 + Scarlett 2i2 at minimum gain), FS_per_V = 0.2045 and FS_per_Pa = 0.002045

        # parameters of stimulus file or audio output device
        'output': {
            'mode': 'file', # 'file' or 'device'
            'sample_rate': 48000,
            'bit_depth': '24 int', # 16/24/32-bit signed integer (e.g. '24 int') or 32-bit floating point ('32 float')
            'num_channels': 1,
            'channel':'all', # which channel chirp stimulus is written to (for files) or output to (for playback devices). 'all' to replicate chirp on every output channel
            'amplitude': 0.5, # amplitude in FS (e.g. 0.5FS = -6dBFS)
            'pre_sweep': 0.5, # silence to include before/after chirp. Only used for stimulus generation, independent from analysis pre/post_sweep
            'post_sweep': 0.5,
            'include_silence': True, # preprend output signal with silence of length pre_sweep + chirp_length + post_sweep for measurement noise floor estimation
            'device': '', # output sound card device name. If blank or otherwise not found, will change to the default output device for the target host API
            'api': 'MME', # sound card host API to target. If blank or otherwise not found, will default to the first element in the DeviceIO.HOST_APIS list (i.e. MME on Windows)
            },
        
        # parameters of input file containing recording of chirp response or audio input device to record response
        'input': {
            'mode': 'file',
            'channel': 1, # which channel to use from input file or capture device
            'file': newproj_response_dir + 'new-project_response.wav', # input file path
            'sample_rate': 48000,
            'capture_length': 4.0, # length of time to record input, in seconds
            'use_output_length': True, # automatically update capture_length to the same length as the output stimulus length (chirp_length + output pre_sweep + output post_sweep + leading silence)
            'device': '',
            'api': 'MME',
            },
        
        # list of measurements
        'measurements': [
            # only providing name and type will populate default measurement parameters
            {'name': 'Frequency Response', # user-defined measurement name
             'type': 'FrequencyResponse'}, # measurement type matching a class name from the measurements module  
            
            {'name': 'Phase Response',
             'type': 'PhaseResponse'},

            {'name': 'Total Harmonic Distortion',
             'type': 'HarmonicDistortion'},
            ]
        }



import yaml
from pathlib import Path

def load_project_file(load_path):
    global project
    with open(load_path) as in_file:
        # todo: add some sort of project format validation
        project = yaml.safe_load(in_file)
    
    global project_file
    project_file = load_path
    
    global working_directory
    working_directory = str(Path(load_path).parent)

def save_project_file(save_path):
    global project
    with open(save_path, 'w') as out_file:
        out_file.write(yaml.dump(project))


