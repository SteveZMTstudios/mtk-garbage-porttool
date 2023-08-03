import re
from io import StringIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from os import walk, getcwd, chdir
import os.path as op
from shutil import rmtree, copytree
import lzma
from sys import stdout
from hashlib import md5
from .bootimg import unpack_bootimg, repack_bootimg
from .imgextractor import Extractor

class proputil:
    def __init__(self, propfile: str):
        proppath = Path(propfile)
        if proppath.exists():
            self.propfd = Path(propfile).open('r+', encoding='utf-8')
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
            if i.startswith(key): return i.rstrip().split('=')[1]
        return None
    
    def setprop(self, key, value) -> None:
        flag: bool = False # maybe there is not only one item
        for index, current in enumerate(self.prop):
            if key in current:
                if not value: value = '' # wtf?
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
    def __init__(self, items: dict, bootimg: str, sysimg: str, portzip: str, genimg: bool = False, stdlog = None):
        self.items = items
        self.sysimg = sysimg
        self.bootimg = bootimg
        self.portzip = portzip
        self.genimg = genimg # if you want system.img
        self.outdir = Path("out")
        if not self.outdir.exists():
            self.outdir.mkdir(parents=True)
        if not stdlog:
            self.std = stdout
        else: self.std = stdlog
        if not self.__check_exist:
            print("文件是否存在检查不通过", file=self.std)
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
        print(f"解压移植包...", file=self.std)
        ziputil.decompress(self.portzip, str(outdir))
    
    def __port_boot(self) -> bool:
        def __replace(src: Path, dest: Path):
            print(f"boot替换 {src} -> {dest}...", file=self.std)
            return Path(src).write_bytes(dest.read_bytes())
        basedir = Path("tmp/base")
        portdir = Path("tmp/port")
        # make new dir
        print("创建boot移植目录", file=self.std)
        if basedir.exists():
            rmtree(basedir)
        if portdir.exists():
            rmtree(portdir)
        
        basedir.mkdir(parents=True)
        portdir.mkdir(parents=True)

        # copy imgs
        print("复制/解压镜像", file=self.std)
        basedir.joinpath("boot.img").absolute().write_bytes(Path(self.bootimg).read_bytes())
        base = basedir.joinpath("boot.img")
        try:
            ziputil.extract_onefile(self.portzip, "boot.img", "tmp/port/")
        except:
            print("Error: 无法从移植包根目录内解压boot.img", file=self.std)
            return False
        port = Path(portdir.joinpath("boot.img").absolute())
        #port.write_bytes(Path("tmp/rom/boot.img").read_bytes())

        # unpack boot.img
        print("解包boot镜像", file=self.std)
        bootutil(str(base)).unpack()
        bootutil(str(port)).unpack()

        # start to port boot
        for item in self.items['flags']:
            item_flag = self.items['flags'][item]
            if not item_flag: continue
            match item:
                case 'replace_kernel':
                    for i in self.items['replace']['kernel']:
                        if basedir.joinpath(i).exists():
                            print(f"替换内核 {i}", file=self.std)
                            __replace(basedir.joinpath(i), basedir.joinpath(i).absolute())
                case 'replace_fstab':
                    for i in self.items['replace']['fstab']:
                        if basedir.joinpath(i).exists():
                            print(f"替换分区表 {i}", file=self.std)
                            __replace(basedir.joinpath(i), basedir.joinpath(i).absolute())
                case 'selinux_permissive':
                    if portdir.joinpath("bootinfo.txt").exists():
                        with portdir.joinpath("bootinfo.txt").open("r+") as f:
                            lines = [i.rstrip() for i in f.readlines()]
                            #f.truncate(0)
                            flag = False
                            for i in lines:
                                if "androidboot.selinux=permissive" in i:
                                    print("已开启selinux宽容，无需操作", file=self.std)
                                    flag = True
                            if flag: continue
                            else:
                                f.truncate(0)
                                for i in lines:
                                    if i.startswith("cmdline:"):
                                        print("开启selinux宽容", file=self.std)
                                        f.write(i+" androidboot.selinux=permissive\n")
                                    else:
                                        f.write(i+'\n')
                case 'enable_adb':
                    if portdir.joinpath("inidrd/default.prop").exists():
                        print("开启adb和调试", file=self.std)
                        with proputil(str(portdir.joinpath("inidrd/default.prop"))) as p:
                            kv = [
                                ('ro.secure', '0'),
                                ('ro.adb.secure', '0'),
                                ('ro.debuggable', '1'),
                                ('persist.sys.usb.config', 'mtp,adb')
                            ]
                            for key, value in kv:
                                p.setprop(key, value)
        
        # repack boot
        print("打包boot镜像", file=self.std)
        bootutil(str(port)).repack()
        outboot = Path(portdir.joinpath("boot-new.img"))
        to = Path("tmp/rom/boot.img")
        to.write_bytes(outboot.read_bytes())
        return True
    
    def __port_system(self):
        def __replace(val: str):
            print(f"替换$base/{i} -> $port/{i}...", file=self.std)
            if base_prefix.joinpath(i).is_dir():
                if port_prefix.joinpath(i).exists():
                    rmtree(port_prefix.joinpath(i))
                copytree(base_prefix.joinpath(i),
                         port_prefix.joinpath(i))
            else:
                port_prefix.joinpath(i).write_bytes(
                    base_prefix.joinpath(i).read_bytes()
                )

        unpack_flag = False
        with open(self.sysimg, 'rb') as f:
            sysmd5 = md5(f.read()).hexdigest()
        md5path = Path("base/system.md5")
        if not md5path.exists():
            md5path.parent.mkdir(parents=True, exist_ok=True)
            md5fd = md5path.open("w")
            md5fd.write(sysmd5)
            readmd5 = ''
            unpack_flag = True
        else:
            md5fd = md5path.open("r+")
            readmd5 = md5fd.readline().rstrip()
        md5fd.close()
        if sysmd5 == readmd5:
            print("检测到system已经解包，无需二次解包以减少移植时间", file=self.std)
        else:
            unpack_flag = True
            md5path.parent.mkdir(parents=True, exist_ok=True)
            syspath = Path("base/system")
            configpath = Path("base/config")
            if syspath.exists():
                rmtree("base/system")
            if configpath.exists():
                rmtree("base/config")
        if unpack_flag:
            print("开始解包system镜像... ", end='', file=self.std)
            Extractor().main(self.sysimg, "base/system")
            print("解包完成", file=self.std)

        base_prefix = Path("base/system")
        port_prefix = Path("tmp/rom/system")
        for item in self.items['flags']:
            item_flag = self.items[item]
            if not item_flag: continue
            if item.startswith("replace_"):
                for i in self.items['replace'][item.split('_')[1]]:
                    if base_prefix.joinpath(i).exists():
                        __replace(i)
                    else:
                        print(f"Warning: {i} 在底包中没有找到，这也许不是什么大问题", file=self.std)
                continue
            match item:
                case 'single_simcard' | 'dual_simcard':
                    print(f"修改手机为[{'单卡' if item == 'single_simcard' else '双卡'}]", file=self.std)
                    with proputil(str(port_prefix.joinpath("build.prop"))) as p:
                        kv = [
                            ('persist.multisim.config', 'ss' if item == 'single_simcard' else 'dsds'),
                            ('persist.radio.multisim.config', 'ss' if item == 'single_simcard' else 'dsds'),
                            ('ro.telephony.sim.count', '1' if item == 'single_simcard' else '2'),
                            ('persist.dsds.enabled', 'false' if item == 'single_simcard' else 'true'),
                            ('ro.dual.sim.phone', 'false' if item == 'single_simcard' else 'true'),
                        ]
                        for key, value in kv:
                            p.setprop(key, value)
                case 'fit_density':
                    print(f"从底包获取dpi并替换到移植包", file=self.std)
                    with proputil(str(port_prefix.joinpath("build.prop"))) as pp, \
                         proputil(str(base_prefix.joinpath("build.prop"))) as bp:
                        print(f"修改移植包build.prop dpi:{bp.getprop('ro.sf.lcd_density')}", file=self.std)
                        pp.setprop('ro.sf.lcd_density', bp.getprop('ro.sf.lcd_density'))
                case 'change_timezone' | 'change_locale' | 'change_model':
                    change_type = item.split('_')[1]
                    keys = []
                    match change_type:
                        case 'timezone':
                            keys = [
                                'persist.sys.timezone',
                            ]
                        case 'locale':
                            keys = [
                                'ro.product.locale',
                            ]
                        case 'model':
                            keys = [
                            'ro.product.manufacturer',
                            'ro.build.product',
                            'ro.product.model',
                            'ro.product.device',
                            'ro.product.board',
                            'ro.product.brand',
                            ]
                    with proputil(str(port_prefix.joinpath("build.prop"))) as pp, \
                         proputil(str(base_prefix.joinpath("build.prop"))) as bp:
                        for key in keys:
                            value = bp.getprop(key)
                            print(f"修改移植包build.prop键值 [{key}]:[{value}]", file=self.std)
                            pp.setprop(key, value)
        return True
    
    def __pack_rom(self):
        for item in self.items['flags']:
            if item == 'use_custom_update-binary':
                print("使用自带的update-binary以解决在twrp刷入报错的问题", file=self.std)
                Path("tmp/rom/META-INF/com/google/android/updater-script").write_bytes(
                    Path("bin/update-binary").read_bytes())
        print("打包卡刷包.....", end='', file=self.std)
        outpath = Path(f"out/{op.basename(self.portzip)}")
        if outpath.exists():
            outpath.unlink()
        ziputil.compress(str(outpath), "tmp/rom/")
        print("完成！", file=self.std)
        return
    
    def __pack_img(self):
        print("打包system.img暂不支持，请使用打包成zip的功能")
        return

    def start(self):
        self.__decompress_portzip()
        self.__port_boot()
        self.__port_system()
        if self.genimg:
            self.__pack_img()
        else: self.__pack_rom()
