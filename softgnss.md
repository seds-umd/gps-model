# SoftGNSS Notes

[SoftGNSS](https://github.com/TMBOC/SoftGNSS) is a working GPS receiver in MATLAB. This is an attempt to reverse engineer it and implement it in Python.

## Files

Files that are important are bolded and elaborated on later.

* geoFunctions - probably stuff for navigation solution, ignoring for now
* include - some of this looks important
  * **calcLoopCoef** - PLL and DLL loop bandwidth
  * checkPhase - related to bit parity
  * CNoVSM - calculate CNo using the variance summing method
  * ephemeris - decodes ephemerides and TOW from bit stream
  * findTransTime - finds time of transmission of a given sample, I think?
  * **generateCAcode** - generates PRN code for a given satellite
  * invert - inverts binary data
  * makeCaTable - generates PRN code for all satellites
  * navPartyChk - runs parity check on navigation word
  * parityCheck - another parity check, might just be a different implementation of previous?
  * preRun - initializes data structures containing tracking information for each channel
  * showChannelStatus - prints status of channels
  * skyPlot - plots sky view from receiver perspective
  * twosComp2dec - two's complement conversion
* **acquisition** - cold start acquisition
* **calculatePseudoranges** - calculates relative pseudoranges for all satellites
* findPreambles - finds preamble in navigation data
* init - wrapping for initialization data and starting script
* initSettings - default settings
* plotAcquisition - plots acquisition results
* plotNavigation - plots navigation results
* plotTracking - plots tracking results
* postNavigation - calculates navigation solutions
* **postProcessing** - the main script
* probeData - plots raw binary data
* setSettings - settings dialog
* **tracking** - code and carrier tracking
* **trackingv** - also code and carrier tracking?
* transTimeTable - create transmit time table

## Acquisition

## Tracking

`tracking.m` and `trackingv.m` are similar, but `trackingv` includes a Kalman filter. We will only focus on `tracking` for now.

Pseudocode:
* For each channel with valid acquisition
  * Advanced through samples by codePhase-1, so we're now at the start of a new code
  * Generate C/A code with 1 sample per chip, then insert addition samples at start and end for wrapping
  * Initialize various variables to 0
  * For each ms of data
    * Set `codePhaseStep` to `codeFreq`/`samplingFreq`
    * Set `blksize` to `ceil((codeLength-remCodePhase) / codePhaseStep)`
    * Read in `blksize` samples
    * Set up early, prompt, and late codes
      * `remCodePhase` to `((blksize-1)*codePhaseStep+remCodePhase)`, by `codePhaseStep`, +-earlyLateSpc for early and late
      * Ceil and add one to the above, then use as index for caCode
    * Update `remCodePhase` to `(tcode(blksize) + codePhaseStep) - 1023.0`
    * Generate carrier replica and mix to get baseband signal
    * Mix baseband signal with early, prompt, late codes and sum results
    * Carrier PLL
      * Error is `atan(Q_P / I_P) / (2pi)`
      * Carrier NCO is `oldNco + tau2/tau1 * (err - oldErr) + err * (0.001/tau1)` (0.001 is summing interval, tau1 and tau2 comes from calcLoopCoef)
    * Code PLL
      * Error is `(abs(early) - abs(late))/(abs(early) + abs(late))`
      * Code NCO is `oldNco + tau2/tau1 * (err - oldErr) + err * (0.001/tau1)` (see note on carrier NCO, but tau1/2 are different)
    * Save results for plotting

## Navigation
