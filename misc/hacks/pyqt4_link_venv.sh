#!/bin/bash
# This hook is run after a new virtualenv is activated.
# ~/.virtualenvs/postmkvirtualenv

libs=( PyQt4 sip.so )

python_version=python$(python -c "import sys; print (str(sys.version_info[0])+'.'+str(sys.version_info[1]))")
echo "python version is " $python_version
get_python_lib_cmd="from distutils.sysconfig import get_python_lib; print (get_python_lib())"
lib_virtualenv_path=$(python -c "$get_python_lib_cmd")
echo virtualenv path is $lib_virtualenv_path

echo $python_version
python_exc=$(which -a ${python_version})
for each in $python_exc; do
  second_last=$last
  last=$each
done
python_sys=$second_last
lib_system_path=$($python_sys -c "$get_python_lib_cmd")
echo path to python version is $lib_system_path

for lib in ${libs[@]}
do
    echo "Symlinking $lib_system_path/$lib to $lib_virtualenv_path/$lib"
    ln -sf $lib_system_path/$lib $lib_virtualenv_path/$lib 
done
