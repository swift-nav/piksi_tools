echo off
setlocal
c:\python35\python setup.py develop
c:\python35\python setup.py install
SET PATH=%PATH%;C:\cygwin\bin;C:\Program Files (x86)\NSIS;C:\Program Files\NSIS;C:\Python35\DLLs;C:\Python35\Scripts;C:\Python35\Lib\site-packages\vtk;C:\Python35\gnuplot\binary;C:\Python35\Lib\site-packages\osgeo;C:\Program Files (x86)\pythonxy\SciTE-3.5.1-4;C:\Program Files (x86)\pythonxy\console;C:\Program Files (x86)\pythonxy\swig;C:\Program Files (x86)\pythonxy\gettext\bin;
python piksi_tools/version.py
make build_console