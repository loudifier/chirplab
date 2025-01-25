import CLProject as clp
import math
import numpy as np
from scipy.signal import fftconvolve
import tempfile
from pathlib import Path
import subprocess
from scipy.io import wavfile
import pandas as pd
import os
from qtpy.QtWidgets import QErrorMessage


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

def generate_stimulus_file(out_path):
    # generate a stimulus file to play on the DUT using the project output parameters
    stimulus = clp.project['output']['amplitude'] * np.concatenate([
        np.zeros(round(clp.project['output']['pre_sweep']*clp.project['output']['sample_rate'])),
        logchirp(clp.project['start_freq'], clp.project['stop_freq'], clp.project['chirp_length'], clp.project['output']['sample_rate']),
        np.zeros(round(clp.project['output']['post_sweep']*clp.project['output']['sample_rate']))])
    if clp.project['output']['include_silence']:
        stimulus = np.concatenate([
            np.zeros(len(stimulus)),
            stimulus])
    
    if clp.project['output']['channel'] == 'all':
        stimulus = np.tile(stimulus, (clp.project['output']['num_channels'], 1)).transpose()
    else:
        stimulus_signal = stimulus
        stimulus = np.zeros((len(stimulus_signal), clp.project['output']['num_channels']))
        stimulus[:, clp.project['output']['channel']-1] = stimulus_signal
    try:
        write_audio_file(stimulus, out_path, clp.project['output']['sample_rate'], clp.project['output']['bit_depth'])
    except PermissionError as ex:
        print(ex)
        if clp.gui_mode:
            error_box = QErrorMessage()
            error_box.showMessage('Error writing stimulus file \n' + str(ex))
            error_box.exec()
    

def read_response():
    # will need to be reworked when adding audio device in/out
    
    # read input file
    if clp.project['use_input_rate']:
        sample_rate = 0
    else:
        sample_rate = clp.project['sample_rate']
    clp.signals['raw_response'] = read_audio_file(clp.project['input']['file'], sample_rate)
    
    #  get only the desired channel
    if clp.signals['raw_response'].ndim > 1: # multiple channels in input file
        response = clp.signals['raw_response'][:,clp.project['input']['channel']-1]
    else:
        response = clp.signals['raw_response']
        
    # determine the position of the captured chirp in the response signal
    response_delay = find_offset(response, clp.signals['stimulus'])
    
    # pad the response if the beginning or end of the chirp is cut off or there isn't enough silence for pre/post sweep (or there is a severe mismatch between stimulus and response). Throw a warning?
    start_padding = max(0, -response_delay) # response_delay should be negative if beginning is cut off
    response_delay = response_delay + start_padding
    end_padding = max(0, len(clp.signals['stimulus']) - (len(response) - response_delay))
    response = np.concatenate([np.zeros(start_padding),
                               response,
                               np.zeros(end_padding)])
    
    # trim the raw response to just the segment aligned with the stimulus
    clp.signals['response'] = response[response_delay:response_delay + len(clp.signals['stimulus'])] # get only the part of the raw response signal where the chirp was detected
    
    # if there is enough silence in the response recording preceeding the chirp, use that portion for noise floor estimation
    if response_delay > len(clp.signals['stimulus']):
        clp.signals['noise'] = response[response_delay-len(clp.signals['stimulus']):response_delay]
    else:
        clp.signals['noise'] = []

def read_audio_file(audio_file, sample_rate=0):
    # convert the input file to a friendly 32-bit floating point format temporary wav file, then reads the file into a numpy array with scipy
    # if a sample rate is given, also resample the input file to the specified rate
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir: # add delete=False if needed for debugging. ignore_cleanup_errors requires python 3.10+
        temp_wav = Path(temp_dir) / 'response.wav'
        if sample_rate:
            result = subprocess.run([clp.sox_path, audio_file, '-b', '32', '-e', 'floating-point', '-r', str(sample_rate), str(temp_wav), '>', Path(temp_dir) / 'soxerr.txt', '2>&1'], shell=True)
        else:
            result = subprocess.run([clp.sox_path, audio_file, '-b', '32', '-e', 'floating-point', str(temp_wav), '>', Path(temp_dir) / 'soxerr.txt', '2>&1'], shell=True)
        sox_out = (Path(temp_dir) / 'soxerr.txt').read_text()
        if result.returncode:
            if 'No such file' in sox_out:
                raise FileNotFoundError(sox_out)
            if 'no handler' in sox_out:
                raise FormatNotSupportedError(sox_out)
            raise Exception(sox_out)
        
        rate, samples = wavfile.read(str(temp_wav))
        return samples

def write_audio_file(samples, out_path, sample_rate=48000, depth='24 int'):
    match depth:
        case '16 int':
            bits = 16
            numtype = 'signed-integer'
        case '24 int':
            bits = 24
            numtype = 'signed-integer'
        case '32 int':
            bits = 32
            numtype = 'signed-integer'
        case '32 float':
            bits = 32
            numtype = 'floating-point'
        case _:
            bits = 24
            numtype = 'signed-integer'
                
    # write the input samples to a temporary 32-bit floating point format, then convert to the desired output format
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_wav = Path(temp_dir) / 'stimulus.wav'
        wavfile.write(temp_wav, sample_rate, samples)
        # sox output is really weird. All output is sent through a weird version of stderr and the only way access it is redirecting stderr *in the shell*.
        # Regardless of settings, result.stdout and result.stderr are always None, but returncode correlates to actual errors (warnings=0, errors=2)
        # subprocess.run() with shell=True is unsafe. Find or write a better audio file IO library at some point. #todo #security
        result = subprocess.run([clp.sox_path, str(temp_wav), '-b', str(bits), '-e', numtype, str(out_path), '2>', str(Path(temp_dir) / 'soxerr.txt')], shell=True)
        if result.returncode:
            with open(Path(temp_dir) / 'soxerr.txt') as e:
                # for writing a file with sox, assume the problem is a permissions error
                soxerr = e.read()
                raise PermissionError(soxerr)

def audio_file_info(file_path):
    # read audio file header using sox
    # subprocess.run() with shell=True is unsafe. Find or write a better audio file IO library at some point. #todo #security
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        result = subprocess.run([clp.sox_path, '--i', str(file_path), '>', Path(temp_dir) / 'soxerr.txt', '2>&1'], shell=True)
        sox_out = (Path(temp_dir) / 'soxerr.txt').read_text()
        
        if result.returncode:
            if 'No such file' in sox_out:
                raise FileNotFoundError(sox_out)
            if 'no handler' in sox_out:
                raise FormatNotSupportedError(sox_out)
            raise Exception(sox_out)

        channels = int(sox_out.splitlines()[2].split(':')[1])
        sample_rate = int(sox_out.splitlines()[3].split(':')[1])
        length_samples = int(sox_out.splitlines()[5].split('=')[1].split(' ')[1])
        numtype = sox_out.splitlines()[8].split(': ')[1]
        return {'channels': channels,
                'sample_rate': sample_rate,
                'length_samples': length_samples,
                'numtype': numtype}

class FormatNotSupportedError(Exception):
    pass

def find_offset(input_sig, find_sig):
    # for two 1D input arrays where a signal similar to find_sig is expected to be somewhere in input_sig, find the position of find_sig in input_sig and return the index of the start of find_sig
    # implemented using cross correlation through fft convolution
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

def freq_points(start_freq, stop_freq, num_points, spacing='log', round_to_whole_freq=False):
    # generate an array of frequency points with log or linear spacing, or log spaced in points per octave
    # for points per octave pass the number of points per octave for num_points and 'octave' for spacing
    if 'lin' in spacing:
        out_points = np.linspace(start_freq, stop_freq, num_points)
    else:
        if spacing=='octave':
            num_octaves = np.log2(stop_freq/start_freq)
            num_points = int(np.ceil(num_octaves * num_points))
        out_points = np.geomspace(start_freq, stop_freq, num_points)
    if round_to_whole_freq:
        out_points = np.unique(np.round(out_points))
    return out_points

def interpolate(x_input, y_input, x_output, linear=True):
    if linear:
        return np.interp(x_output, x_input, y_input)
    else:
        return np.interp(np.log(x_output), np.log(x_input), y_input)