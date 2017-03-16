from traitsui.api import TextEditor
import numpy as np

class MultilineTextEditor(TextEditor):
  """
  Override of TextEditor Class for a multi-line read only
  """

  def init(self, parent=TextEditor(multi_line=True)):
    parent.read_only = True
    parent.multi_line = True

def plot_square_axes(plot, xnames, ynames):
  try:
    if type(xnames) is str:
      xs = plot.data.get_data(xnames)
      ys = plot.data.get_data(ynames)
      minx = min(xs)
      maxx = max(xs)
      miny = min(ys)
      maxy = max(ys)
    else:
      concatx = np.concatenate([plot.data.get_data(xname) for xname in xnames])
      concaty = np.concatenate([plot.data.get_data(yname) for yname in ynames])
      minx = min(concatx)
      maxx = max(concatx)
      miny = min(concaty)
      maxy = max(concaty)
    rangex = maxx - minx
    rangey = maxy - miny
    try:
      aspect = float(plot.width) / plot.height
    except:
      aspect = 1
    if aspect * rangey > rangex:
      padding = (aspect * rangey - rangex) / 2
      plot.index_range.low_setting = minx - padding
      plot.index_range.high_setting = maxx + padding
      plot.value_range.low_setting = miny
      plot.value_range.high_setting = maxy
    else:
      padding = (rangex / aspect - rangey) / 2
      plot.index_range.low_setting = minx
      plot.index_range.high_setting = maxx
      plot.value_range.low_setting = miny - padding
      plot.value_range.high_setting = maxy + padding
  except:
    sys.__stderr__.write(traceback.format_exc() + '\n')
