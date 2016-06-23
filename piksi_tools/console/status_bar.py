
from time import sleep, strftime
from threading import Thread
from traits.api import Str, Instance, Dict, HasTraits,Bool,  Int, Button, List, Enum, Property
from traitsui.api import Item, Label, View, HGroup, VGroup, VSplit, HSplit, Tabbed, \
                         InstanceEditor, EnumEditor, ShellEditor, Handler, Spring, \
                         TableEditor, UItem, StatusItem
import traitsui
import random



class statusBar(HasTraits):
   # text=Str
    CSV_or_JASON = Bool
    count_changes= Int(0)
    string = Str
    fix_type = Str
    time= Str
    num_sats = Int(0)
    my_button_trait = Button('...')
    logging_button=Button('Log')
    logging = Str
    #test= Str

    def _my_button_trait_fired(self):
        self.logging = random.choice(['c:/test/mylog','c:/test/JSON'])
    

    def _time_default(self):
        thread = Thread(target = self._clock)
        thread.setDaemon(True)
        thread.start()

        return ''


    def _clock(self):
        """ Update the statusbar time once every second.                                                   
        """
    
        
        while True:
            self.time = strftime('%I:%M:%S %p')
            self.count_changes +=1
            self.num_sats +=1
            if self.num_sats>=10:
                self.num_sats =10
            if self.count_changes < 5:
                self.fix_type = 'SPS'
            elif self.count_changes>=5 and self.count_changes <10:
                self.fix_type = 'float RTK'
            else:
                self.fix_type = 'fixed RTK'
                
            #print(self.fix_type)
            sleep(1.0)
    
    def _CSV_or_JASON_changed(self):
        if(self.CSV_or_JASON):
            #self.count_changes = 1
            self.string = 'hello'
        else:
            #self.count_changes = 0
            self.string= 'no'



view1 = View(
      #  Label('Type into the text editor box:'),
      #  Item(name = 'text', label='useless'),
    
        HGroup(
            Item('', label='SERIAL PORT:', emphasized=True, tooltip='Serial Port that Piksi is connected to'),
            Item('', label='COM1'),
            Item('', label='FIX TYPE:', emphasized = True, tooltip='Piksi Mode: SPS, Float RTK, Fixed RTK'),
            Item('fix_type', show_label=False, style = 'readonly'),
            Item('', label='#SATS:', emphasized=True, tooltip='Number of satellites acquired by Piksi'),
            Item('num_sats', show_label=False, style = 'readonly'),
            Item('logging_button', show_label= False, bgcolor = (0.8,0.8,0.8), tooltip='Start or stop logging'),
            Item('CSV_or_JASON',label='JSON?', emphasized=True, tooltip='File as JSON, default settings are CSV'),
            Item('string',show_label=False, style = 'readonly'),
            Item('my_button_trait',show_label=False, tooltip='Select location to store log files'),
            Item('logging',show_label=False, style = 'readonly'),
            ),
    title = 'Status Bar',
    resizable = True,
    statusbar = [ StatusItem(name = 'time',   width = 85) ]

)



sam = statusBar()
sam.configure_traits(view=view1)
