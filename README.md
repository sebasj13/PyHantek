# <p align="center"> PyHantek</p>

PyHantek provides basic funtionality to communicate with digital storage oscilloscopes using the HANTEK protocol. The provided software (TTScope) is not very usable - this repository enables pythonic interaction to handle almost any use case.

All my testing was done on a Voltcraft DSO-1062D, however this protocol should apply to all DSOs in the DSO5xxxBs series. 

## Installation

The prerequisites for this library are <a href="https://github.com/pyusb/pyusb">PyUSB</a> and <a href="https://github.com/numpy/numpy">numpy</a>. These can be installed via:

```console
pip install pyusb numpy
```
One you have these installed and cloned this repository or downloaded the files, you need to install the drivers for the oscilloscope. Connect the oscilloscope via USB, then start Zadig, which can be downloaded from <a href="https://zadig.akeo.ie/">here</a>. After installion the WinUSB driver, you can use this library. 
<b><br>NOTE: This step breaks the functionality of the included software (TTScope).</br></b>

## Documentation

<p align = "center">WORK IN PROGRESS</p>
Many of the functions are taken from: <a href="https://github.com/titos-carrasco/DSO5102P-Python">DSO5102P-Python</a>


## Contributing
Any help us greatly appreciated! Sources that document the HANTEK protocol can be found <a href="https://elinux.org/Das_Oszi_Protocol">here</a> and <a href="https://www.mikrocontroller.net/articles/Datei:SysDATA_v1.0.zip">here</a>.


