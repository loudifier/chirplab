chirp_length: 1.0
chirplab_version: 0.3
FS_per_Pa: 1.0
FS_per_V: 1.0
input:
  channel: 1
  file: speaker-response.wav
  mode: file
measurements:
- fade_in: 10
  fade_out: 25
  name: Frequency Response
  output:
    max_auto: true
    max_freq: 20000
    min_auto: true
    min_freq: 20.0
    num_points: 24
    round_points: false
    spacing: octave
    unit: dBFS
  type: FrequencyResponse
  window_end: 50
  window_mode: adaptive
  window_start: 10
- fade_in: 0.1
  fade_out: 0.5
  name: THD
  output:
    max_auto: true
    max_freq: 10800.0
    min_auto: true
    min_freq: 20.0
    num_points: 24
    round_points: false
    spacing: octave
    unit: dB
  start_harmonic: 2
  stop_harmonic: 10
  type: HarmonicDistortion
  window_end: 0.9
  window_start: 0.1
- fade_in: 0.1
  fade_out: 0.5
  name: HOHD
  output:
    max_auto: true
    max_freq: 2160.0
    min_auto: true
    min_freq: 20.0
    num_points: 24
    round_points: false
    spacing: octave
    unit: dB
  start_harmonic: 10
  stop_harmonic: 20
  type: HarmonicDistortion
  window_end: 0.9
  window_start: 0.1
output:
  amplitude: 0.5
  bit_depth: 24 int
  channel: all
  include_silence: true
  mode: file
  num_channels: 1
  post_sweep: 0.5
  pre_sweep: 0.5
  sample_rate: 48000
post_sweep: 0.05
pre_sweep: 0.05
sample_rate: 48000
start_freq: 20.0
stop_freq: 20000
use_input_rate: true
