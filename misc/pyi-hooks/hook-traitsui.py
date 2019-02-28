from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.utils.hooks import copy_metadata

qt = collect_submodules('traitsui.qt4')

hiddenimports = qt

datas = collect_data_files('traitsui') + copy_metadata('traitsui')
