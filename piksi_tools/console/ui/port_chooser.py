from pkg_resources import resource_filename
from pyface.image_resource import ImageResource
from traits.api import Bool, Enum, HasTraits, Int, List, Str
from traitsui.api import EnumEditor, HGroup, Item, Label, Spring, VGroup, View

flow_control_options_list = ['None', 'Hardware RTS/CTS']
cnx_type_list = ['Serial/USB', 'TCP/IP']

BAUD_LIST = [57600, 115200, 230400, 921600, 1000000]


icon = ImageResource(
    'icon1',
    search_path=[resource_filename('piksi_tools', 'console/images')]
)

class PortChooser(HasTraits):
    ports = List()
    port = Str(None)
    mode = Enum(cnx_type_list)
    flow_control = Enum(flow_control_options_list)
    ip_port = Int(55555)
    ip_address = Str('192.168.0.222')
    choose_baud = Bool(True)
    baudrate = Int()
    traits_view = View(
        VGroup(
            Spring(height=8),
            HGroup(
                Spring(width=-2, springy=False),
                Item(
                    'mode',
                    style='custom',
                    editor=EnumEditor(
                        values=cnx_type_list, cols=2, format_str='%s'),
                    show_label=False)),
            HGroup(
                VGroup(
                    Label('Serial Device:'),
                    Item(
                        'port',
                        editor=EnumEditor(name='ports'),
                        show_label=False), ),
                VGroup(
                    Label('Baudrate:'),
                    Item(
                        'baudrate',
                        editor=EnumEditor(values=BAUD_LIST),
                        show_label=False,
                        visible_when='choose_baud'),
                    Item(
                        'baudrate',
                        show_label=False,
                        visible_when='not choose_baud',
                        style='readonly'), ),
                VGroup(
                    Label('Flow Control:'),
                    Item(
                        'flow_control',
                        editor=EnumEditor(
                            values=flow_control_options_list, format_str='%s'),
                        show_label=False), ),
                visible_when="mode==\'Serial/USB\'"),
            HGroup(
                VGroup(
                    Label('IP Address:'),
                    Item(
                        'ip_address',
                        label="IP Address",
                        style='simple',
                        show_label=False,
                        height=-24), ),
                VGroup(
                    Label('IP Port:'),
                    Item(
                        'ip_port',
                        label="IP Port",
                        style='simple',
                        show_label=False,
                        height=-24), ),
                Spring(),
                visible_when="mode==\'TCP/IP\'"), ),
        buttons=['OK', 'Cancel'],
        close_result=False,
        icon=icon,
        width=400,
        title='Swift Console - Select Piksi Interface', )

    def __init__(self, ports, baudrate=None):
        try:
            self.ports = ports
            # self.ports = [p for p, _, _ in s.get_ports()]
            if baudrate not in BAUD_LIST:
                self.choose_baud = False
            self.baudrate = baudrate
        except TypeError:
            pass
