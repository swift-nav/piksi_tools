
from piksi_tools import generate_settings_doc as gen
import os
def test_generation():
  gen.main()
  assert os.path.isfile('docs/settings.pdf')


