#!/bin/bash
rm /usr/bin/python
ln -s /cygdrive/c/Python27/python.exe /usr/bin/python
echo 'PATH=$PATH:"/cygdrive/c/Python27/DLLs:/cygdrive/c/Python27/Scripts:/cygdrive/c/Python27/Lib/site-packages/vtk:/cygdrive/c/Python27/gnuplot/binary:/cygdrive/c/Python27/Lib/site-packages/osgeo:/cygdrive/c/Program Files (x86)/pythonxy/SciTE-3.5.1-4:/cygdrive/c/Program Files (x86)/pythonxy/console:/cygdrive/c/Program Files (x86)/pythonxy/swig:/cygdrive/c/Program Files (x86)/pythonxy/gettext/bin"' >> .bashrc

