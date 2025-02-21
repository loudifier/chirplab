# Chirplab feature roadmap

Features in each subheading are ordered roughly in order of prioritization. This list is not exhaustive and will change over time as smaller items are completed and removed, new ideas are added, and overall project priorities shift. Many smaller items not captured in this list are scattered throughout the code with `todo:` comments.

## Input and Output
- [x] WAV file input and output
- [ ] Audio interface/sound card input and output
- Most likely implemented using the PyAudio PortAudio bindings
- [ ] ASIO input and output
- Open source software typically does not redistribute the Steinberg libraries needed to support ASIO interfaces. At minimum, the process to compile PyAudio or otherwise make ASIO interfaces available in Chirplab should be clearly documented
- [ ] Other audio file formats
- Technically, any audio file format that SoX understands is already supported by manually entering the full filename and extension and/or using the 'All files' filter in the input file picker.
- [ ] Native file I/O without using SoX as an intermediary
- SoX is used as a robust, fast, lightweight, and readily available universal file conversion utility. This comes with the downside of needing a separate download and potentially introduces security issues to work around SoX's strange stderr output. The SciPy wavfile module works for 16 and 32 bit int and 32 bit floating point WAV files, but does not properly handle common 24 bit WAV files or any other formats, so the current solution is to use SoX to convert input files to a 32 bit floating point WAV (including any resampling) and read the WAV with wavfile (and vice versa for output files).
- [ ] Multi-channel/Multi-file/Multi-capture support
- Analyzing additional signals is trivial on top of implementing the actual signal analysis in any given measurement, but managing the UI and how the user *expects* multi-channel analysis to work gets very complex very quickly. How multiple measurement inputs are selected, how outputs are displayed with or without measurement noise floor(s), storing measurement outputs and adding new measurement traces, and handling a geometrically expanding set of UI interactions can derail the development of other features and measurements.

## Measurements
- [x] Frequency Response
    - [x] Raw, fixed window, and adaptive windowing modes
    - [ ] Fixed window impulse response/energy time curve visualizer GUI
    - [ ] Option for windowing GUI elements to express times in distance (probably only meters for simplicity)
- [x] Harmonic Distortion
    - [ ] Option to set parameters of reference fundamental frequency response measurement parameters (e.g. use raw or fixed window for faster processing)
    - [ ] Experiment with adaptive windowing and/or add parameters for harmonic impulse windowing (likely very slow)
- [ ] Phase Response
    - [ ] Requires some experimentation to see how robustly t0 can be located. Absolute vs relative phase, and relative to what reference? Is a pilot tone required, and how do you compensate for significant phase shift of the pilot tone itself?
    - [ ] How does noise impact phase response? Is a measurement noise floor calculation meaningful?
- [ ] Tracking Filter
    - [ ] Implement at least bandpass, highpass filters
    - [ ] Implement filter tracking, signal level metering (moving RMS and peak hold that are consistent across different chirp lengths, sweep rates)
    - [ ] Implement crest factor output option
    - [ ] Come up with a better name that communicates this can be used for fundamental frequency response, rub and buzz, or even harmonic analysis. Maybe leave as-is but implement measurement presets with more descriptive names (e.g. "THD+N", "Rub and Buzz Crest Factor")
- [ ] Spectral Analysis
    - [ ] Experiment with builtin STFT options in SciPy/NumPy or roll a custom version that is easier to derive measurement data from
    - [ ] Parameters
    - Component of the signal selected for data output - fundamental, harmonics, non-harmonic noise, THD+N, etc.
        - Need to handle different unit outputs (and how fundamental reference is calculated for distortion metrics)
    - Min/max analyzed harmonic
    - Include noise below fundamental
    - [ ] Experiment with different ways to assign time-frequency bins to different parts of the signal.
    - Integrating power of the lobe with the nearest peak and troughs on either side of a fundamental/harmonic frequency bin works, but is relatively slow and succeptible to noise in adjacent bins
    - Generate a chirp of fundamental and each harmonic and multiply its STFT with the response STFT to get harmonic power. Apply tracking notch filters for fundamental and each harmonic and take the difference between that STFT and the full STFT for non-harmonic distortion.
    - Option for non-normalized non-harmonic noise, to highlight narrowband noise/ringing that is triggered by the stimulus (see if that provides better separation of vertical bands on spectrogram than non-harmonic noise normalized to the stimulus fundamental)
    - [ ] Spectrogram plot
    - Color coding for different components of the signal - fundamental, harmonics, noise
    - Any way to clearly communicate measurement noise floor in spectrogram? Maybe something like how cameras show clipping with zerba overlay?
- [ ] Impulse Response
    - [ ] Parameters
    - IR length, pre-post trimming
    - Windowing fade in/out
    - Wrapped with time aligned to t0 or shifted/rolled to the right
    - Normalized or raw - may need to specify floating point if outputting to WAV (verify SoX/wavfile behavior with floating point values greater than 1.0)
    - [ ] Option to output and/or plot as Energy Time Curve, T60 (or generic Tn value)
    - [ ] Measurement noise floor output off by default when outputting IR waveforms, but could be very useful for qualitative comparison in IR and ETC plots
- [ ] Waterfall
    - [ ] What should the configuration parameters and output look like?
    - [ ] 3D plotting, figure out how to communicate measurement noise floor without making it too busy

## General features
- [ ] Real units calibration - some sort of 'Pa per FS' and 'Volts per FS' conversion factors so output units can be expressed in real units
    - [ ] Automatic calibration using a reference tone
    - [ ] General unit conversion function (or class? interface?) in CLAnalysis to convert raw measurement outputs in FS to common units
- [ ] Pilot tone. Required by some commercial audio software, need to investigate to determine what measurements actually require precise timing that can't be determined by cross correlation
- [ ] Input and/or output EQ. Similar to multi-channel/multi-file analysis, this is heavily dependant on interface, but with added complications of how filtering is implemented (direct amplitude vs time, FIR filtering, biquad sum-of-sections, how an EQ table is interpolated, etc...)

## Graphical User Interface
- [x] Chirp settings, input and output tab
    - [x] Break individual parameter sections into their own classes? Probably a good idea to keep things organized before adding hardware IO
    - [ ] Ability to plot stimulus response against frequency X axis
- [x] Project file save/load
    - [ ] (As things evolve and breaking changes are made) Implement project version upgrading. At the very least a warning message that project files that don't match the current Chirplab version may fail in interesting ways
    - [ ] Some sort of measurement preset save/load? E.g. .clm files that are a subset of the full project .clp file. Extend new measurement dialog to be able to load a measurement preset, etc.
- [ ] Overall look and feel
    - [ ] Any accessibility issues will be prioritized. Please raise an issue if you identify UI elements with poor contrast or color contrast, excessive flashing, etc.
        - [x] Graph colors are blue/orange by default, avoid red/green
        - [ ] Qt elements are pretty good about keyboard controls and I tried to include hotkeys for all standard options, but there are a lot of UI elements, so I may have missed some
        - [ ] I am not very familiar with screen readers, but I believe Qt should have good support natively
    - [ ] Proper scaling over a wide range of DPI
    - [ ] Speed up plotting, particularly chirp tab updating every time a chirp parameter spinbox is clicked
    - [ ] Bundle Windows exe in such a way that GUI launches without console window and CLI/GUI both output to stdout. Currently bundled with console showing so error messages and CLI output goes to the console. https://pyinstaller.org/en/stable/feature-notes.html#automatic-hiding-and-minimization-of-console-window-under-windows
- [ ] Undo/redo - a lot of work with many edge cases that need to be handled, but would be really nice to have

## Command Line Interface
- [x] Run all measurements in a project file and output measurement data
    - [ ] Switches to override individual project parameters. Analyze different input files/channels from the same project file, change data output directory, output file names, etc.
- [ ] Generate stimulus file from parameters or a project file
- [ ] Measure calibration tone from a file and apply the calibration to a project file
- [ ] Performance optimization to improve batch file processing
- Compilation, caching, etc to improve Python startup time
- Delaying GUI imports until needed to keep CLI from having to import Qt libraries. A bit of a pain in the early stages of development, can lead to circular imports and heisenbugs - revisit after major GUI efforts like device IO have been completed.

## Other
- [ ] Build automation - just PyInstaller scripts or full blown GitHub Workflow stuff
- [ ] Documentation...
    - [ ] Quick Start guide
    - [ ] Project file format
    - [ ] Calibration guide (including clear explanation of 3dB RMS vs peak compensation)
    - [ ] Explanations of individual measurements. How they work, what the different parameters do, what the outputs mean, etc.
- [ ] Testing
- End-to-end tests of measurement outputs from different input signals, rather than typical TDD-style units tests
- Ground truth comparisons to other measurement software
- Synthetic signals that simulate different noise floors, direct harmonics, modeled speaker nonlinearities, etc.
- Actual acoustic measurements with different speakers and microphones
