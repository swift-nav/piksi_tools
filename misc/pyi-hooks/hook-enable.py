from PyInstaller.utils.hooks import collect_submodules, collect_data_files

qt = collect_submodules('enable.qt4')
trait_defs_ui_qt = collect_submodules('enable.trait_defs.ui.qt4')
savage_trait_defs_ui_qt = collect_submodules('enable.savage.trait_defs.ui.qt4')

hiddenimports = qt + trait_defs_ui_qt + savage_trait_defs_ui_qt

datas = collect_data_files('enable')
