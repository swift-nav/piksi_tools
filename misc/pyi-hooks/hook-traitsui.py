from PyInstaller.utils.hooks import collect_submodules, collect_data_files

qt = collect_submodules('traitsui.qt4')

hiddenimports = qt

datas = collect_data_files('traitsui')
