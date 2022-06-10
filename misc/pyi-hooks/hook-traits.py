from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.utils.hooks import copy_metadata

distutils = collect_submodules('distutils')
etsconfig = collect_submodules('traits.etsconfig')

hiddenimports = distutils + etsconfig

datas = collect_data_files('traits') + copy_metadata('traits')
