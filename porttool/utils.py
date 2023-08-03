import re
from io import StringIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from os import walk
import os.path as op
import lzma

class proputil:
    def __init__(self, propfile: str):
        proppath = Path(propfile)
        if proppath.exists():
            self.propfd = Path(propfile).open('r+')
        else:
            raise FileExistsError(f"File {propfile} does not exist!")
        self.prop = self.__loadprop

    @property
    def __loadprop(self) -> list:
        return self.propfd.readlines()

    def getprop(self, key: str) -> str | None:
        '''
        recive key and return value or None
        '''
        for i in self.prop:
            if key in i: return i.rstrip().split('=')[1]
        return None
    
    def setprop(self, key, value) -> None:
        flag: bool = False # maybe there is not only one item
        for index, current in enumerate(self.prop):
            if key in current:
                self.prop[index] = current.split('=')[0] + '=' + value + '\n'
                flag = True
        if not flag:
            self.prop.append(
                key + '=' + value + '\n'
            )

    def save(self):
        self.propfd.seek(0, 0)
        self.propfd.truncate()
        self.propfd.writelines(self.prop)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb): # with proputil('build.prop') as p:
        self.save()
        self.propfd.close()

class updaterutil:
    def __init__(self, fd: StringIO):
        #self.path = Path(path)
        self.fd = fd
        if not self.fd:
            raise IOError("fd is not valid!")
        self.context = self.__parse_commands
    
    @property
    def __parse_commands(self): # This part code from @libchara-dev
        self.fd.seek(0, 0) # set seek from start
        commands = re.findall(r'(\w+)\((.*?)\)', self.fd.read())
        parsed_commands = [[command, *(arg[0] or arg[1] or arg[2] for arg in re.findall(r'(?:"([^"]+)"|(\b\d+\b)|(\b\S+\b))', args))] for command, args in commands]
        return parsed_commands

class ziputil:
    def __init__(self):
        pass
    
    def decompress(zippath: str, outdir: str):
        with ZipFile(zippath, 'r') as zipf:
            zipf.extractall(outdir)
    
    def compress(zippath: str, indir: str):
        with ZipFile(zippath, 'w', ZIP_DEFLATED) as zipf:
            for root, dirs, files in walk(indir):
                for file in files:
                    file_path = op.join(root, file)
                    zip_path = op.relpath(zippath, indir)
                    zipf.write(file_path, zip_path)

class xz_util:
    def __init__(self):
        pass

    def compress(src_file_path, dest_file_path):
        with open(src_file_path, 'rb') as src_file:
            with lzma.open(dest_file_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
