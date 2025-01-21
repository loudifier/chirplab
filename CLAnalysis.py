import math
import numpy as np
from scipy.fftpack import fft, ifft, fftfreq
from scipy.signal import fftconvolve
from scipy import interpolate


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