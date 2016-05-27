echo off
setlocal
c:\python27\python setup.py develop
c:\python27\python setup.py install
SET PATH=%PATH%;C:\cygwin\bin;C:\Program Files (x86)\NSIS;C:\Program Files\NSIS;C:\Python27\DLLs;C:\Python27\Scripts;C:\Python27\Lib\site-packages\vtk;C:\Python27\gnuplot\binary;C:\Python27\Lib\site-packages\osgeo;C:\Program Files (x86)\pythonxy\SciTE-3.5.1-4;C:\Program Files (x86)\pythonxy\console;C:\Program Files (x86)\pythonxy\swig;C:\Program Files (x86)\pythonxy\gettext\bin;
python piksi_tools/version.py
make build_console