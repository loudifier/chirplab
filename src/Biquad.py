import numpy as np

# Somewhat simplified and naive implementation of a biquad linear filter, plus a handful of biquad coefficient calculations
# Could probably do something more performant with scipy.signal.lfilter and keeping track of zi, but this works for how filtering is applied in Chriplab

class Biquad():
    # filter object that keeps track of coefficients and signal state.
    # uses 6 coefficients b[0-2] and a[0-2]
    # if only two a coefficients are given, a and b coefficients are assumed to be normalized such that a[0]=1 and input parameter a[0] is intended to be used as filter a[1], input a[1] as filter a[2]
    def __init__(self, b=[1,0,0], a=[1,0,0]):
        self.b = b
        if len(a)<3:
            self.a = [1,a[0],a[1]]
        else:
            # normalize coefficients such that a[0]=1
            self.b = [b[0]/a[0], b[1]/a[0], b[2]/a[0]]
            self.a = [1, a[1]/a[0], a[2]/a[0]]
        
        #initialize previous signal values to 0, 2 samples each for previous input signal and previous output signal
        self.x_m1 = 0
        self.x_m2 = 0
        self.y_m1 = 0
        self.y_m2 = 0
    
    def process(self, x):
        # ensure input is array_like
        ndim = np.ndim(x)
        if ndim==0:
            x = [x]

        # process and return as a numpy array if input is an array
        if isinstance(x, np.ndarray):
            y = np.zeros(len(x))
        else:
            y = [0]*len(x)

        for n in range(len(x)):
            # apply coefficients in typical Direct Form I
            y[n] = self.b[0]*x[n] + self.b[1]*self.x_m1 + self.b[2]*self.x_m2 - self.a[1]*self.y_m1 - self.a[2]*self.y_m2
            
            # shift previous samples to keep track of filter state
            self.x_m2 = self.x_m1
            self.x_m1 = x[n]
            self.y_m2 = self.y_m1
            self.y_m1 = y[n]

        if ndim==0:
            # return a single sample if input is a single sample
            return y[0]
        return y


# Collection of functions to calculate 2nd order filter coefficients
# Most calculations are originally from RBJ cookbook, using https://github.com/loudifier/Biquad-Cookbook as a reference to verify output accuracy

def lowpass_coeff(F0, Q, Fs):
    # 2nd order lowpass filter
    w0 = 2*np.pi*F0/Fs
    alpha = np.sin(w0)/(2*Q)

    # calculate raw coefficients
    a = [1 + alpha,
         -2 * np.cos(w0),
         1 - alpha]
    
    b = [(1 - np.cos(w0))/2,
         1 - np.cos(w0),
         (1 - np.cos(w0))/2]
    
    # normalize such that a0=1
    a[1] /= a[0]
    a[2] /= a[0]
    b[0] /= a[0]
    b[1] /= a[0]
    b[2] /= a[0]
    a[0] /= a[0]

    return b, a

def highpass_coeff(F0, Q, Fs):
    # 2nd order highpass filter
    w0 = 2*np.pi*F0/Fs
    alpha = np.sin(w0)/(2*Q)

    # calculate raw coefficients
    a = [1 + alpha,
         -2 * np.cos(w0),
         1 - alpha]
    
    b = [(1 + np.cos(w0))/2,
         -(1 + np.cos(w0)),
         (1 + np.cos(w0))/2]
    
    # normalize such that a0=1
    a[1] /= a[0]
    a[2] /= a[0]
    b[0] /= a[0]
    b[1] /= a[0]
    b[2] /= a[0]
    a[0] /= a[0]

    return b, a

def bandpass_coeff(F0, Q, Fs):
    # constant peak bandpass filter, peaking at 0dB
    w0 = 2*np.pi*F0/Fs
    alpha = np.sin(w0)/(2*Q)

    # calculate raw coefficients
    a = [1 + alpha,
         -2 * np.cos(w0),
         1 - alpha]
    
    b = [alpha,
         0,
         -alpha]
    
    # normalize such that a0=1
    a[1] /= a[0]
    a[2] /= a[0]
    b[0] /= a[0]
    b[2] /= a[0]
    a[0] /= a[0]

    if np.ndim(F0):
        b[1] = np.zeros(len(F0))

    return b, a

def notch_coeff(F0, Q, Fs):
    # notch filter
    w0 = 2*np.pi*F0/Fs
    alpha = np.sin(w0)/(2*Q)

    # calculate raw coefficients
    a = [1 + alpha,
         -2 * np.cos(w0),
         1 - alpha]
    
    b = [1,
         -2 * np.cos(w0),
         1]
    
    # normalize such that a0=1
    a[1] /= a[0]
    a[2] /= a[0]
    b[0] /= a[0]
    b[1] /= a[0]
    b[2] /= a[0]
    a[0] /= a[0]

    return b, a
