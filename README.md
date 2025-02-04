# Chirplab
Chirplab is an audio and acoutics measurement suite based on fast open-loop log-swept sine chirp generation, capture, and analysis.

![Chirplab logo](img/splash.png)

Chirplab is built on Python, NumPy/SciPy, Qt, and other open source software and is released under the [MIT license](LICENSE)

## Overview
Chirplab can be used as a standalone GUI for interactively examining measurement data and experimenting with different project parameter settings, or entirely via a command line interface using plaintext project file input and measurement data output. This allows a seamless transision between R&D and automated or manufacturing workflows, and even allows custom Chirplab measurements to be incorporated into other audio test software that can call external programs as part of a measurement sequence.

### Main GUI
- Configure chirp parameters
- Define input file
- Add and configure measurements and measurement outputs
- Save and load project files

### Command line interface
- Process a project file and output measurement data

### Comparison to other audio measurement systems
--- This will be eventually filled out with graphs comparing Chirplab measurements to other free and commercial audio measurement suites ---

## Measurement noise floor
In most respects Chirplab is entirely conventional and all of the processing that it performs is based on DSP literature, readily available research papers, and experimentation to produce measurement outputs that are roughly equivalent to those produced by commercial audio test systems. However, Chirplab includes a unique feature that helps you avoid misleading data and understand whether a measurement is providing insight into the performance of a device or system under test, or if it is just showing you the noise floor of your measurement system.

As an example, here is a graph showing the frequency response of the same speaker measured with two different microphones:

![Speaker response measured with different micropohnes](img/fr-comparison.png)

The speaker was driven at the same level with the microphones at the same distance from the speaker in the same room, and the responses have been normalized to account for different microphone sensitivity. The microphones have flat, closely matched responses, and they show nearly identical response from the speaker.

However, when these microphones are used to measure the distortion of the speaker they show significantly different results.

![Speaker distortion measured with different microphones](img/thd-comparison.png)

The only notable performance difference between the microphones is that one has a lower noise floor. Most audio measurement systems allow you to measure noise floor as an individual measurement, but the connection between the system noise floor and its impact on other measurements is almost never communicated. Chirplab captures a section of the system noise floor equal in length to the stimulus chirp, processes that through the same calculations as the regular response, and gives you an estimate of the noise floor *for that measurement*.

![Speaker distortion vs estimated measurement noise floor](img/thd-noise-comparison.png)

## Project Status
Chirplab v0.1 is in an initial "minimally usable" state, supporting file input and output and two basic measurements - Frequency Response and Harmonic Distortion. It will eventually support audio interface (sound card) playback and recording, acoustic/electrical signal level calibration, and several additional measurement types, including equivalent measurements to those that you would expect from commercial audio measurement systems and some entirely unique distortion metrics. See the [roadmap](ROADMAP.md) for a high level list of currently implemented and planned features. Contributions are welcome.

If you have a specific feature request not on the roadmap, find a bug, have an audio file or signal that does not play nicely with Chirplab, etc. please [raise an issue](https://github.com/loudifier/chirplab/issues).