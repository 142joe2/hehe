import os
import sys

if sys.platform == 'win32':
    gtk_bin = r'C:\GTK\bin'
    if os.path.isdir(gtk_bin):
        os.add_dll_directory(gtk_bin)
