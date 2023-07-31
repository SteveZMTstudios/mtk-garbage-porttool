#!/usr/bin/env python3
from tkinter import Tk
from .porttool import (
    MyUI
)

if __name__ == '__main__':
    root = Tk()
    root.title("MTK Port Tool")
    root.geometry("320x500")

    myapp = MyUI(root)
    myapp.pack(side='top', fill='both', padx=5, pady=5, expand='yes')

    root.update()
    root.mainloop()