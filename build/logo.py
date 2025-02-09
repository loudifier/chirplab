import matplotlib.pyplot as plt
import numpy as np
from scipy.signal.windows import hann
from scipy.io import wavfile

import sys
sys.path.insert(0, '../src')
from CLAnalysis import logchirp

fs = 48000
chirp_length = 5

logo_pixels = [
'                                                                  ',
'                                                                  ',
'                                                                  ',
'        XXXX    XX      XX                XX          XX          ',
'       XXXXXX   XX      XX                XX          XX          ',
'      XXXXXXXX  XX                        XX          XX          ',
'      XXX   XX  XX XX       X XX  X XX    XX    XX X  XX X        ',
'      XX    XX  XXXXXX  XX  XXXX  XXXXX   XX   XXXXX  XXXXX       ',
'      XX        XXX XX  XX  XXX   XXXXXX  XX  XXX XX  XX  XX      ',
'      XX        XX  XX  XX  XX    XX  XX  XX  XX  XX  XX  XX      ',
'      XX    XX  XX  XX  XX  XX    XX  XX  XX  XX  XX  XX  XX      ',
'      XX    XX  XX  XX  XX  XX    XX  XX  XX   XX XX  XX XXX      ',
'       XXXXXX   XX  XX  XX  XX    XXXXX   XX    XXXX  XXXXX       ',
'                                  XX                              ',
'                                  XX                              ',
'                                                                  ',
'                                                                  ',
'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
'                                                                  ',
'                                                                  ']

logo_width = len(logo_pixels[0])
logo_height = len(logo_pixels)

chirp_start = fs/2/250
chirp_stop = fs/2/logo_height

window_width = int(fs * chirp_length / logo_width)
pixel_window = hann(window_width)

logo_signal = np.zeros(round(fs * chirp_length))

#plt.plot(logo_signal)
#plt.show()

for row in range(logo_height):
    harmonic = logo_height-row
    harmonic_mult = 1+0.02*harmonic
    harmonic_signal = logchirp(chirp_start*harmonic, chirp_stop*harmonic, chirp_length, fs)
    #plt.plot(harmonic_signal)

    for column in range(logo_width):
        column_mult = 1+0.02*column
        if logo_pixels[row][column]=='X':
            logo_signal[window_width*column:window_width*column+window_width] += harmonic_signal[window_width*column:window_width*column+window_width] * harmonic_mult * column_mult
            if column<logo_width-1 and logo_pixels[row][column+1]=='X':
                logo_signal[window_width*column+int(window_width/2):window_width*column+window_width+int(window_width/2)] += harmonic_signal[window_width*column+int(window_width/2):window_width*column+window_width+int(window_width/2)]  * harmonic_mult * column_mult
#plt.show()

logo_signal = logo_signal/max(logo_signal)

nfft = 1024

plt.specgram(logo_signal, NFFT=nfft, pad_to=nfft*16, mode='magnitude', noverlap=int(nfft/2), cmap='binary', vmin=-55, vmax=-30)
plt.yscale('log')
plt.ylim(1/100, 1)
plt.xlim(nfft, int(len(logo_signal)/2)-nfft)
plt.show()

#wavfile.write('logo.wav', fs, logo_signal)





nfft = 512

icon = wavfile.read('../examples/new-project_response.wav')[1]
plt.specgram(icon, NFFT=nfft, pad_to=nfft*32, mode='magnitude', noverlap=int(nfft/2), cmap='binary', vmin=100, vmax=155)
plt.yscale('log')
plt.xlim(27000, 53000)
plt.ylim(0.001, 1.0)
plt.show()