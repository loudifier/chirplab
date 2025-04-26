import CLProject as clp
import math
import numpy as np
from scipy.signal import fftconvolve
import tempfile
from pathlib import Path
import subprocess
from scipy.io import wavfile
import pandas as pd
from qtpy.QtWidgets import QErrorMessage, QMessageBox
import sys
import requests
from zipfile import ZipFile
from scipy.fftpack import fft, ifft


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

def chirp_time_to_freq(start_freq, stop_freq, length, time):
    # f(t) = start_freq * k^t
    # k = (stop_freq/start_freq)^(1/length)
    k = (stop_freq/start_freq)**(1/length)
    return start_freq * (k**time)

def chirp_freq_to_time(start_freq, stop_freq, length, freq):
    k = (stop_freq/start_freq)**(1/length)
    return np.log(freq/start_freq) / np.log(k)

def generate_stimulus():
    # generate the signal used as the reference chirp stimulus for chirp analysis
    # chirp signal is padded at the beginning/end with zeros of length clp.project['pre/post_sweep']
    clp.signals['stimulus'] = np.concatenate([
        np.zeros(round(clp.project['pre_sweep']*clp.project['sample_rate'])),
        logchirp(clp.project['start_freq'], clp.project['stop_freq'], clp.project['chirp_length'], clp.project['sample_rate']),
        np.zeros(round(clp.project['post_sweep']*clp.project['sample_rate']))])
    # if this is updated at some point probably refactor and also update harmonic_chirp() in ImpulsiveDistortion.measure()

def generate_output_stimulus():
    # generate a multi-channel stimulus signal using the project output parameters
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
    
    return stimulus

def generate_stimulus_file(out_path):
    # generate a stimulus file to play on the DUT using the project output parameters
    stimulus = generate_output_stimulus()

    try:
        write_audio_file(stimulus, out_path, clp.project['output']['sample_rate'], clp.project['output']['bit_depth'])
    except PermissionError as ex:
        print(ex)
        if clp.gui_mode:
            error_box = QErrorMessage()
            error_box.showMessage('Error writing stimulus file \n' + str(ex))
            error_box.exec()
    
def read_response():
    # get the desired channel from the input signal, locate the chirp in the signal, and trim/pad to time align with the reference stimulus
    # assumes input signal is already captured/loaded into clp.signals['raw_response'] and clp.signals['stimulus'] has been generated
    
    # get only the desired channel
    if clp.signals['raw_response'].ndim > 1: # multiple channels in input file
        response = clp.signals['raw_response'][:,clp.project['input']['channel']-1]
    else:
        response = clp.signals['raw_response']

    # resample input if necessary
    if clp.project['sample_rate'] != clp.IO['input']['sample_rate']:
        if clp.project['use_input_rate']:
            clp.project['sample_rate'] = clp.IO['input']['sample_rate'] # this should handle CLI settings, GUI should always update itself so sample rate display matches input rate
        else:
            response = resample(response, clp.IO['input']['sample_rate'], clp.project['sample_rate'])
        
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
        command = [clp.sox_path, str(find_file(audio_file)), '-b', '32', '-e', 'floating-point']
        if sample_rate:
            command += ['-r', str(sample_rate)]
        command += [str(temp_wav), '>', str(Path(temp_dir) / 'soxerr.txt'), '2>&1']
        if sys.platform == 'win32':
            result = subprocess.run(command, shell=True)
        else:
            result = subprocess.run([' '.join(command)], shell=True)
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
            print('unrecognized bit depth, using 24-bit int')
            bits = 24
            numtype = 'signed-integer'
                
    # write the input samples to a temporary 32-bit floating point format, then convert to the desired output format
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_wav = Path(temp_dir) / 'stimulus.wav'
        wavfile.write(temp_wav, sample_rate, samples)
        # sox output is really weird. All output is sent through a weird version of stderr and the only way access it is redirecting stderr *in the shell*.
        # Regardless of settings, result.stdout and result.stderr are always None, but returncode correlates to actual errors (warnings=0, errors=2)
        # subprocess.run() with shell=True is unsafe. Find or write a better audio file IO library at some point. #todo #security
        command = [clp.sox_path, str(temp_wav), '-b', str(bits), '-e', numtype, str(out_path), '2>', str(Path(temp_dir) / 'soxerr.txt')]
        if sys.platform == 'win32':
            result = subprocess.run(command, shell=True)
        else:
            result = subprocess.run([' '.join(command)], shell=True)
        if result.returncode:
            with open(Path(temp_dir) / 'soxerr.txt') as e:
                # for writing a file with sox, assume the problem is a permissions error
                soxerr = e.read()
                raise PermissionError(soxerr)

def resample(input_signal, input_sample_rate, output_sample_rate):
    # resample using sox, essentially the same process as write_audio_file and read_audio_file smashed together
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir: # add delete=False if needed for debugging. ignore_cleanup_errors requires python 3.10+
        temp_wav = Path(temp_dir) / 'input.wav'
        wavfile.write(temp_wav, input_sample_rate, input_signal)

        resampled_wav = Path(temp_dir) / 'resampled.wav'
        command = [clp.sox_path, str(temp_wav), '-b', '32', '-e', 'floating-point', '-r', str(output_sample_rate), str(resampled_wav), '>', str(Path(temp_dir) / 'soxerr.txt'), '2>&1']
        if sys.platform == 'win32':
            result = subprocess.run(command, shell=True)
        else:
            result = subprocess.run([' '.join(command)], shell=True)
        sox_out = (Path(temp_dir) / 'soxerr.txt').read_text()
        if result.returncode:
            if 'No such file' in sox_out:
                raise FileNotFoundError(sox_out)
            if 'no handler' in sox_out:
                raise FormatNotSupportedError(sox_out)
            raise Exception(sox_out)
        
        rate, samples = wavfile.read(str(resampled_wav))
        return samples

def audio_file_info(file_path):
    # read audio file header using sox
    # subprocess.run() with shell=True is unsafe. Find or write a better audio file IO library at some point. #todo #security
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        command = [clp.sox_path, '--i', str(find_file(file_path)), '>', str(Path(temp_dir) / 'soxerr.txt'), '2>&1']
        if sys.platform == 'win32':
            result = subprocess.run(command, shell=True)
        else:
            result = subprocess.run([' '.join(command)], shell=True)
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

def find_file(filename):
    # convert local or relative file paths to full file path
    if not Path(filename).is_absolute():
        # search for file relative to the Chirplab working directory
        if Path(clp.working_directory, filename).exists():
            return Path(clp.working_directory, filename)
        
        # search for file relative to the current project file
        if Path(Path(clp.project_file).parent, filename).exists():
            return Path(Path(clp.project_file).parent, filename)
        
    # if file was not found (or was already a full path) then just return it and let the caller decide what to do
    return filename

def find_offset(input_sig, find_sig):
    # for two 1D input arrays where a signal similar to find_sig is expected to be somewhere in input_sig, find the position of find_sig in input_sig and return the index of the start of find_sig
    # implemented using cross correlation through fft convolution
    correlation = fftconvolve(input_sig, find_sig[::-1]) # reverse 1 signal for *cross* correlation
    return np.argmax(np.abs(correlation)) - len(find_sig) # cross correlation peaks at point where signals align, offset by reversed signal

def save_xlsx(measurements, out_path):
    # todo: get measurement data from one or more measurements and save the output data in a single excel file
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
    
def FS_to_unit(input_FS, output_unit): # todo: extend to also calculate dB, %, etc?
    match output_unit:
        case 'FS':
            return input_FS
        case 'dBFS':
            return 20*np.log10(input_FS)
        case 'dBSPL':
            ninety_four_dBSPL = 20*np.log10(1/0.00002) # 0dBSPL = 20uPa
            return 20*np.log10(input_FS / clp.project['FS_per_Pa']) + ninety_four_dBSPL
        case 'dBV':
            return 20*np.log10(input_FS / clp.project['FS_per_V'])
        case 'Pa':
            return input_FS / clp.project['FS_per_Pa']
        case 'V':
            return input_FS / clp.project['FS_per_V']

def fftconv(signal, kernel):
    # scipy/numpy (de)convolution doesn't produce the expected results, seemingly due to how they handle array lengths/shapes.
    # this plays nicely with Chirplab managing array lengths on its own and using impulse responses deconvolved through a simple division of stimulus and response spectrums
    
    # ensure signal and kernel to the same length
    max_length = max(len(signal), len(kernel))
    sig_pad = np.concatenate([signal, np.zeros(max_length - len(signal))])
    kern_pad = np.concatenate([kernel, np.zeros(max_length - len(kernel))])
    
    # apply kernel to the signal in the frequency domain and convert back to the time domain
    return ifft(fft(sig_pad) * fft(kern_pad))

def max_in_intervals(x_input, y_input, x_output, linear=True):
    # similar application to interpolate(), but returns the maximum value in y_input for each interval around x_output points. Assumes x_input and x_output are in ascending order

    y_output = np.zeros(len(x_output))

    # loop through input points to find the maximum in the intervals around each output point. Ugly and brute force approach, but handles a lot of corner cases that would be difficult to get right with a solution that uses pandas .rolling()
    j = 0 # keep track of which output point is being calculated
    for i in range(len(x_input)):

        # skip everything below the lowest output point (but still initialize min_point)
        if x_input[i] < x_output[0]:
            min_point = i
            continue
        
        # find the dividing line between the current point and the next point
        if j == len(x_output) - 1: # skip everything above the highest output point
            boundary = x_output[-1]
        else:
            if linear:
                boundary = (x_output[j] + x_output[j+1]) / 2
            else:
                boundary = np.exp((np.log(x_output[j]) + np.log(x_output[j+1])) / 2)
        
        # find the last input point for the current output point
        if x_input[i] < boundary:
            continue

        # get the max value in the interval around the current output point
        y_output[j] = max(abs(y_input[min_point:i]))

        # set up to find the boundaries for the next output point
        min_point = i
        j += 1
        if j == len(x_output):
            break

    return y_output

def check_sox():
    if sys.platform == 'win32':
        # first check of sox is available on the PATH
        result = subprocess.run(['sox', '-h', '>nul', '2>&1'], shell=True)
        if result.returncode==0: # sox found on PATH
            clp.sox_path = 'sox' # just call the version on the PATH
        else:
            # sox not found on PATH, check if local copy has been downloaded to default location expected by CLProject
            if not Path(clp.sox_path).exists():
                # no local copy has been downloaded, prompt the user to download
                if clp.gui_mode:
                    message_box = QMessageBox()
                    message_box.setWindowTitle('Download SoX?')
                    message_box.setText('Chirplab requires SoX for audio processing. Would you like to download SoX?')
                    message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    download = message_box.exec() == QMessageBox.Yes
                else:
                    response = input('Chirplab requires SoX for audio processing. Would you like to download SoX? [Y/n]\n')
                    if not response:
                        response = 'Y'
                    download = 'Y'.casefold() in response.casefold()

                if download:
                    try:
                        print('Downloading SoX from ' + clp.sox_dl_url + '...')
                        with tempfile.TemporaryFile() as sox_temp:
                            content = requests.get(clp.sox_dl_url, stream=True).content
                            sox_temp.write(content)
                            sox_zip = ZipFile(sox_temp, 'r')
                            sox_zip.extractall(clp.bin_dir) # creates target folder and/or merges zip contents with target folder contents, no need to check for/create bin folder
                            # todo: add something to test that sox is working correctly?
                            #     Sox executable works fine for non-audio commands (--version, etc) even without any of its DLLs
                    except:
                        print('error while downloading SoX')
                        sys.exit()
                else: # just quit if user doesn't want to download sox
                    sys.exit()

    else: # assume non-Windows is some standardish unixlike with `which` and/or user will be savvy enough to figure out installing sox on their own
        clp.sox_path = 'sox'
        result = subprocess.run(['which', 'sox'])
        if result.returncode:
            print('Chirplab requires SoX for audio processing. SoX is usually available via standard sources, e.g. `sudo apt install sox`')
            sys.exit()
