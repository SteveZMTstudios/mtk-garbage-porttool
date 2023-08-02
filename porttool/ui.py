from tkinter import (
    ttk,
    Toplevel,
    scrolledtext,
    StringVar,
    Canvas,
)
from tkinter.filedialog import askopenfilename
from os import getcwd
from pathlib import Path
from .configs import *

class FileChooser(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("请选择要一直的底包的boot, system和要移植的zip卡刷包")
        
        self.portzip = StringVar()
        self.basesys = StringVar()
        self.baseboot = StringVar()
        self.frame = []
        self.__setup_widgets()
        self.focus()
    
    def __setup_widgets(self):
        def __match(val) -> str:
            match val:
                case 0: return "移植包路径"
                case 1: return "此设备boot镜像"
                case 2: return "此设备system镜像"
                case _: return ""
        def __choose_file(val: StringVar):
            val.set(askopenfilename(initialdir=getcwd()))
        
        for index, current in enumerate([self.portzip, self.baseboot, self.basesys]):
            frame = ttk.Frame(self)
            label = ttk.Label(frame, text=__match(index), width=16)
            entry = ttk.Entry(frame, textvariable=current, width=40)
            button = ttk.Button(frame, text="选择文件", command=lambda x=current: __choose_file(x))
            self.frame.append([frame, label, entry, button])
        for i in self.frame:
            for index, widget in enumerate(i):
                if index == 0: # frame
                    widget.pack(side='top', fill='x', padx=5, pady=5)
                    continue
                if index == 2: # entry
                    widget.pack(side='left', fill='x', padx=5, pady=5)
                    continue
                widget.pack(side='left', padx=5, pady=5)
        bottomframe = ttk.Frame(self)
        bottombutton = ttk.Button(bottomframe, text='确定', command=self.destroy)
        bottombutton.pack(side='right', padx=5, pady=5)
        bottomframe.pack(side='bottom', fill='x', padx=5, pady=5)
    
    def get(self) -> list:
        """
        return boot.img, system.img, portzip.zip path
        """
        self.wait_window()
        return [
            self.baseboot.get(),
            self.basesys.get(),
            self.portzip.get(),
            ]

class LogLabel(scrolledtext.ScrolledText):
    def __init__(self, parent):
        super().__init__(parent)
        #self.vars = []

    def write(self, *vars, end='\n'):
        #self.vars = []
        for i in vars:
            self.insert('end', i)
            #self.vars.append(i)
        #self.insert('end', end)

    def flush(self): pass # have no idea how to flush on text widget

    def print(self, *vars, end='\n'):
        print(vars, end=end, file=self)

class MyUI(ttk.Labelframe):
    def __init__(self, parent):
        super().__init__(parent, text="MTK 低端机移植工具")
        self.chipset_select = StringVar(value='mt65')
        self.pack_type = StringVar(value='zip')
        self.log = LogLabel(self)
        self.__setup_widgets()
    
    def __start_port(self):
        files = boot, system, portzip = FileChooser(self).get()
        for i in files:
            if not Path(i).exists():
                self.log.print(f"File {i} does not exist!")
                return

    def __setup_widgets(self):
        def __scroll_event(event):
            number = int(-event.delta / 2)
            actcanvas.yview_scroll(number, 'units')
        def __scroll_func(event):
            actcanvas.configure(scrollregion=actcanvas.bbox("all"), width=300, height=180)
        # label of support devices
        optlabel = ttk.Label(self)

        opttext = ttk.Label(optlabel, text="芯片类型", anchor='e')
        optmenu = ttk.OptionMenu(optlabel, self.chipset_select, support_chipset[0], *support_chipset)

        opttext.pack(side='left', padx=5, pady=5, expand='no')
        optmenu.pack(side='left', fill='x', padx=5, pady=5, expand='no')

        optlabel.pack(side='top', fill='x')

        # Frame of support action
        actframe = ttk.Labelframe(self, text="支持的移植条目", height=180)
        
        actcanvas = Canvas(actframe, )
        actscroll = ttk.Scrollbar(actframe, orient='vertical', command=actcanvas.yview)

        actcanvas.configure(yscrollcommand=actscroll.set)
        actcanvas.configure(scrollregion=(0, 0, 300, 180))
        actcanvas.configure(yscrollincrement=1)
        actcanvas.bind("<MouseWheel>", __scroll_event)

        actscroll.pack(side='right', fill='y')
        actcanvas.pack(side='right', fill='x', expand='yes', anchor='e')
        actframe.pack(side='top', fill='x', expand='yes')
        actcvframe = ttk.Frame(actcanvas)
        actcanvas.create_window(0, 0, window=actcvframe, anchor='nw')
        actcvframe.bind("<Configure>", __scroll_func)

        for i in range(10):
            ttk.Checkbutton(actcvframe, text='TEST %d' %i).pack(side='top', fill='x')

        # label of buttons
        buttonlabel = ttk.Label(self)
        buttonport = ttk.Button(self, text="一键移植", command=self.__start_port)
        buttonport.pack(side='top', fill='x', padx=5, pady=5, expand='yes')
        buttoncheck1 = ttk.Checkbutton(buttonlabel, text="输出为zip卡刷包", variable=self.pack_type, onvalue='zip')
        buttoncheck2 = ttk.Checkbutton(buttonlabel, text="输出为img镜像", variable=self.pack_type, onvalue='img')

        buttoncheck1.grid(column=0, row=1, padx=5, pady=5)
        buttoncheck2.grid(column=1, row=1, padx=5, pady=5)
        buttonlabel.pack(side='top', padx=5, pady=5, fill='x', expand='yes')

        # log label
        self.log.pack(side='top', padx=5, pady=5, fill='both', expand='yes')
        for i in "TEST MESSAGE1", "TEST MESSAGE2", "TEST MESSAGE3":
            print(i, file=self.log, flush=True)