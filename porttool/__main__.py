#!/usr/bin/env python3
from tkinter import Tk
from .ui import (
    MyUI
)

def main():
    root = Tk()
    root.title("MTK Port Tool")
    #root.geometry("860x480")

    myapp = MyUI(root)
    myapp.pack(side='top', fill='both', padx=5, pady=5, expand='yes')

    root.update()
    root.mainloop()