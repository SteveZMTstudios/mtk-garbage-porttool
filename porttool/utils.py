import re
from io import StringIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from os import walk, getcwd, chdir
import os.path as op
from shutil import rmtree
import lzma
from .bootimg import unpack_bootimg, repack_bootimg

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
        self.propfd.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb): # with proputil('build.prop') as p:
        self.save()

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
    
    def extract_onefile(zippath: str, filename: str, outpath: str):
        with ZipFile(zippath, 'r') as zipf:
            zipf.extract(filename, outpath)
    
    def compress(zippath: str, indir: str):
        with ZipFile(zippath, 'w', ZIP_DEFLATED) as zipf:
            for root, dirs, files in walk(indir):
                for file in files:
                    file_path = op.join(root, file)
                    zip_path = op.relpath(op.abspath(file_path), op.abspath(indir))
                    zipf.write(file_path, zip_path)

class xz_util:
    def __init__(self):
        pass

    def compress(src_file_path, dest_file_path):
        with open(src_file_path, 'rb') as src_file:
            with lzma.open(dest_file_path, 'wb') as dest_file:
                dest_file.write(src_file.read())

class bootutil:
    def __init__(self, bootpath):
        self.bootpath = op.abspath(bootpath)
        self.bootdir = op.dirname(self.bootpath)
        self.retcwd = getcwd()
    
    def unpack(self):
        chdir(self.bootdir)
        unpack_bootimg(self.bootpath)
        chdir(self.retcwd)
    
    def repack(self):
        chdir(self.bootdir)
        repack_bootimg()
        chdir(self.retcwd)
    
    def __entry__(self):
        return self

    def __exit__(self, *vars):
        chdir(self.retcwd)

class portutils:
    def __init__(self, items: dict, bootimg: str, sysimg: str, portzip: str, genimg: bool = False):
        self.items = items
        self.sysimg = sysimg
        self.bootimg = bootimg
        self.portzip = portzip
        self.genimg = genimg # if you want system.img
        if not self.__check_exist:
            print("文件是否存在检查不通过")
            return
    
    @property
    def __check_exist(self) -> bool:
        for i in (self.sysimg, self.bootimg, self.portzip):
            if not Path(i).exists():
                return False
        return True

    def __decompress_portzip(self):
        outdir = Path("tmp/rom")
        if outdir.exists():
            rmtree(outdir)
        outdir.mkdir(parents=True)
        ziputil.decompress(self.portzip, str(outdir))
    
    def __port_boot(self) -> bool:
        def __replace(src: Path, dest: Path):
            return Path(src).write_bytes(dest.read_bytes())
        basedir = Path("tmp/base")
        portdir = Path("tmp/port")
        # make new dir
        print("创建boot移植目录")
        if basedir.exists():
            rmtree(basedir)
        if portdir.exists():
            rmtree(portdir)
        
        basedir.mkdir(parents=True)
        portdir.mkdir(parents=True)

        # copy imgs
        print("复制/解压镜像")
        basedir.joinpath("boot.img").absolute().write_bytes(Path(self.bootimg).read_bytes())
        base = basedir.joinpath("boot.img")
        try:
            ziputil.extract_onefile(self.portzip, "boot.img", "tmp/port/")
        except:
            print("Error: 无法从移植包根目录内解压boot.img")
            return False
        port = Path(portdir.joinpath("boot.img").absolute())
        #port.write_bytes(Path("tmp/rom/boot.img").read_bytes())

        # unpack boot.img
        print("解包boot镜像")
        bootutil(str(base)).unpack()
        bootutil(str(port)).unpack()

        # start to port boot
        for item in self.items['flags']:
            item_flag = self.items['flags'][item]
            match item:
                case 'replace_kernel':
                    if not item_flag: continue
                    for i in self.items['replace']['kernel']:
                        if basedir.joinpath(i).exists():
                            print(f"替换内核 {i}")
                            __replace(basedir.joinpath(i), basedir.joinpath(i).absolute())
                case 'replace_fstab':
                    if not item_flag: continue
                    for i in self.items['replace']['fstab']:
                        if basedir.joinpath(i).exists():
                            print(f"替换分区表 {i}")
                            __replace(basedir.joinpath(i), basedir.joinpath(i).absolute())
                case 'selinux_permissive':
                    if not item_flag: continue
                    if portdir.joinpath("bootinfo.txt").exists():
                        with portdir.joinpath("bootinfo.txt").open("r+") as f:
                            lines = [i.rstrip() for i in f.readlines()]
                            #f.truncate(0)
                            flag = False
                            for i in lines:
                                if "androidboot.selinux=permissive" in i:
                                    print("已开启selinux宽容，无需操作")
                                    flag = True
                            if flag: continue
                            else:
                                f.truncate(0)
                                for i in lines:
                                    if i.startswith("cmdline:"):
                                        print("开启selinux宽容")
                                        f.write(i+" androidboot.selinux=permissive\n")
                                    else:
                                        f.write(i+'\n')
                case 'enable_adb':
                    if not item_flag: continue
                    if portdir.joinpath("inidrd/default.prop").exists():
                        print("开启adb和调试")
                        with proputil(str(portdir.joinpath("inidrd/default.prop"))) as p:
                            kv = [
                                ('ro.secure', '0'),
                                ('ro.adb.secure', '0'),
                                ('ro.debuggable', '1'),
                                ('persist.sys.usb.config', 'mtp,adb')
                            ]
                            for key, value in kv:
                                p.setprop(key, value)
        return True
    
    def start(self):
        self.__decompress_portzip()
        self.__port_boot()
