
# configure_traits_view.py -- Sample code to demonstrate
#                             configure_traits()

from traits.api import HasTraits, Str, Int
from traitsui.api import View, Item
import traitsui

class SimpleEmployee(HasTraits):
    first_name = Str
    last_name = Str
    department = Str
    employee_number = Str
    salary = Int

view1 = View(Item(name = 'first_name'),
             Item(name = 'last_name'),
             Item(name = 'department'))

sam = SimpleEmployee()
sam.configure_traits(view=view1)
