# module for sharing globals throughout chirplab

# project dictionary containing parameters of log chirp used for signal generation and analysis, signal input and output, etc
project = {}

# signals updated from chirp tab and used for analysis in measurements. Stimulus, response, impulse response, etc.
signals = {}

# information to keep track of input and output file or device - will change a lot when implementing device IO
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
bin_dir = 'bin\\' # external binaries called at runtime
sox_path = bin_dir + 'sox-14.4.2\\sox.exe'
sox_dl_url = 'https://sourceforge.net/projects/sox/files/sox/14.4.2/sox-14.4.2-win32.zip/download'


# when loading project files from older versions of chirplab, the project may be able to be upgraded for compatibility with current version
CHIRPLAB_VERSION = 0


# constants
MIN_CHIRP_LENGTH = 0.1 # min/max chirp length in seconds
MAX_CHIRP_LENGTH = 60
MIN_CHIRP_FREQ = 0.01
MAX_ZERO_PAD = 10.0 # max length pre/post sweep length in seconds
OUTPUT_SAMPLE_RATES = [8000, 16000, 44100, 48000, 96000, 192000]
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
PLOT_PEN_WIDTH = 3


# default project parameters
def new_project():
    global project
    project = {
        'chirplab_version': CHIRPLAB_VERSION,
        'project_name': 'New Project',
        
        # chirp parameters
        'start_freq': 100, # chirp starting frequency in Hz
        'stop_freq': 20000,
        'chirp_length': 1.0, # length in seconds
        
        # chirp analysis parameters
        'pre_sweep': 0.05, # silence before start of chirp included in analysis window, length in seconds
        'post_sweep': 0.05,
        'sample_rate': 48000, # sample rate in Hz used for all analysis
        
        # parameters of stimulus file or audio output device
        'output': {
            'mode': 'file', # 'file' or 'device'
            'sample_rate': 48000,
            'bit_depth': '24 int',
            'num_channels': 1,
            'channel':'all', # which channel chirp stimulus is written to (for files) or output to (for playback devices). 'all' to replicate chirp on every output channel
            'amplitude': 0.5, # amplitude in FS (e.g. 0.5FS = -6dBFS)
            'pre_sweep': 0.5, # silence to include before/after chirp. Only used for stimulus generation, independent from analysis pre/post_sweep
            'post_sweep': 0.5,
            'include_silence': True, # preprend output signal with silence of length pre_sweep + chirp_length + post_sweep for measurement noise floor estimation
            },
        
        # parameters of input file containing recording of chirp response or audio input device to record response
        'input': {
            'mode': 'file',
            'channel': 1, # which channel to use from input file or capture device
            'file': 'response.wav', # input file path
            },
        
        # list of measurements
        'measurements': [
            {
                'name': 'Frequency Response', # user-defined measurement name
                'type': 'FrequencyResponse', # measurement type matching a class name from the measurements module
                'params': {} # if empty params will be generated from default in measurement class
                },
            {
                'name': 'Total Harmonic Distortion',
                'type': 'HarmonicDistortion',
                'params': {}
                }
            ]
        }




