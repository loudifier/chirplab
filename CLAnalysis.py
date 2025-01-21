import CLProject as clp
import math
import numpy as np
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal import fftconvolve
from scipy import interpolate
import tempfile
from pathlib import Path
import subprocess
from scipy.io import wavfile
import pandas as pd
import os


# module with helper functions for chirp analysis, mostly math stuff

def logchirp(start_freq, stop_freq, length, sample_rate):
    # generate the samples of a log-swept sine chirp signal given
    # start and stop frequencies in Hz
    # length in seconds
    # sample rate in Hz
    length_samples = round(length*sample_rate) # round length to the nearest sample
    length_exact = length_samples/sample_rate # actual length in seconds after rounding
    t = np.arange(length_samples)/sample_rate # array of timestamps for each sample
    
    # calculate chirp value at each timestamp from log-swept sine chirp formula
    # x(t) = sin(K*(exp(t/L)-1))
    # where K is the sweep rate as a function of the start and stop frequencies and chirp length
    # and exp(t/L) is the instantaneous frequency at any point in time
    f_scalar = (2*math.pi*start_freq*length)/math.log(stop_freq/start_freq)
    f_exp = (math.log(stop_freq/start_freq)*t)/length_exact
    return np.sin(f_scalar * (np.exp(f_exp)-1))

def generate_stimulus():
    # generate the signal used as the reference chirp stimulus for chirp analysis
    # chirp signal is padded at the beginning/end with zeros of length clp.project['pre/post_sweep']
    clp.signals['stimulus'] = np.concatenate([
        np.zeros(round(clp.project['pre_sweep']*clp.project['sample_rate'])),
        logchirp(clp.project['start_freq'], clp.project['stop_freq'], clp.project['chirp_length'], clp.project['sample_rate']),
        np.zeros(round(clp.project['post_sweep']*clp.project['sample_rate']))])

def read_response():
    # will need to be reworked when adding audio device in/out
    
    # read input file
    clp.signals['raw_response'] = read_audio_file(clp.project['input']['file'])
    
    #  get only the desired channel
    if clp.signals['raw_response'].ndim > 1: # multiple channels in input file
        response = clp.signals['raw_response'][:,clp.project['input']['channel']-1]
    else:
        response = clp.signals['raw_response']
        
    # determine the position of the captured chirp in the response signal
    response_delay = find_offset(response, clp.signals['stimulus'])
    
    # trim the raw response to just the segment aligned with the stimulus
    clp.signals['response'] = response[response_delay:response_delay + len(clp.signals['stimulus'])] # get only the part of the raw response signal where the chirp was detected
    
    # if there is enough silence in the response recording preceeding the chirp, use that portion for noise floor estimation
    if response_delay > len(clp.signals['stimulus']):
        clp.signals['noise'] = response[response_delay-len(clp.signals['stimulus']):response_delay]
    else:
        clp.signals['noise'] = []

def read_audio_file(audio_file):
    # convert the input file to a friendly 32-bit floating point format temporary wav file, then reads the file into a numpy array with scipy
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir: # add delete=False if needed for debugging. ignore_cleanup_errors requires python 3.10+
        temp_wav = Path(temp_dir) / 'response.wav'
        subprocess.run([clp.sox_path, audio_file, '-b', '32', '-e', 'floating-point', str(temp_wav)])
        rate, samples = wavfile.read(str(temp_wav))
        return samples
    
def find_offset(input_sig, find_sig):
    # for two 1D input arrays where a signal similar to find_sig is expected to be somewhere in input_sig, find the position of find_sig in input_sig and return the index of the start of find_sig
    # implemented using cross correlation through fft convolution
    print('todo: handle chirp cut off in response') # need to pad response when chirp (+pre/post_sweep) in response is cut off. Offset negative when beginning is cut off. read_response() should throw index out of bounds when end is cut off. Might also have alignment issues in case of severe mismatch between recorded chirp and stimulus.
    correlation = fftconvolve(input_sig, find_sig[::-1]) # reverse 1 signal for *cross* correlation
    return np.argmax(np.abs(correlation)) - len(find_sig) # cross correlation peaks at point where signals align, offset by reversed signal

def save_csv(measurement, out_dir=''):
    # get measurement data and save it to a CSV file at the target location
    out_frame = pd.DataFrame({'Frequency (Hz)':measurement.out_freqs, measurement.params['output']['unit']:measurement.out_points})
    if any(measurement.out_noise):
        out_frame['measurement noise floor'] = measurement.out_noise
    with open(os.path.join(out_dir, clp.project['project_name'] + '_' + measurement.name + '.csv'), 'w', newline='') as out_file:
        out_file.write(measurement.name + '\n')
        out_frame.to_csv(out_file, index=False)

def save_xlsx(measurements, out_path):
    # get measurement data from one or more measurements and save the output data in a single excel file
    pass