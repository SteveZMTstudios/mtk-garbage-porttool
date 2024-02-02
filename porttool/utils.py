import glob
import lzma
import os.path as op
import re
import subprocess
from hashlib import md5
from os import walk, getcwd, chdir, symlink, readlink, name as osname, stat, unlink
from pathlib import Path
from shutil import rmtree, copytree
from sys import stdout
from zipfile import ZipFile, ZIP_DEFLATED

from .boot_patch import BootPatcher, parseMagiskApk
from .bootimg import unpack_bootimg, repack_bootimg
from .configs import (
    make_ext4fs_bin,
    magiskboot_bin,
    img2simg_bin
)
from .img2sdat import main as img2sdat
from .imgextractor import Extractor
from .sdat2img import main as sdat2img

if osname == 'nt':
    from ctypes import windll, wintypes

tool_author = 'affggh'
tool_version = '1.1145141919810'


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
        flag: bool = False  # maybe there is not only one item
        for index, current in enumerate(self.prop):
            if key in current:
                if not value: value = ''  # wtf?
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

    def __exit__(self, exc_type, exc_val, exc_tb):  # with proputil('build.prop') as p:
        self.save()


class updaterutil:
    def __init__(self, fd):
        # self.path = Path(path)
        self.fd = fd
        if not self.fd:
            raise IOError("fd is not valid!")
        self.content = self.__parse_commands

    @property
    def __parse_commands(self):  # This part code from @libchara-dev
        self.fd.seek(0, 0)  # set seek from start
        commands = re.findall(r'(\w+)\((.*?)\)', self.fd.read().replace('\n', ''))
        parsed_commands = [
            [command, *(arg[0] or arg[1] or arg[2] for arg in re.findall(r'(?:"([^"]+)"|(\b\d+\b)|(\b\S+\b))', args))]
            for command, args in commands]
        return parsed_commands

    def generate(self, author: str, version: str, partitions: dict):  # This part code from @libchara-dev
        def add_quotes_if_needed(arg):
            return arg if arg.isdigit() else f'"{arg}"'

        if not partitions.get("system") or not partitions.get("boot"):
            return None
        # 将多行项目合并为单行
        self.fd.seek(0, 0)
        updater_script = self.fd.read()
        updater_script = updater_script.replace('\n', '')

        pattern = r'(\w+)\((.*?)\)'
        commands = re.findall(pattern, updater_script)

        # 筛选并保留symlink、set_metadata_recursive和set_metadata命令
        filtered_commands = [
            (command, *(arg[0] or arg[1] or arg[2] for arg in re.findall(r'(?:"([^"]+)"|(\b\d+\b)|(\b\S+\b))', args)))
            for command, args in commands if command in {'symlink', 'set_metadata_recursive', 'set_metadata'}]

        # 将命令和参数转换为字符串
        updater_script_content = [f"{command}({', '.join(map(add_quotes_if_needed, args))});" for command, *args in
                                  filtered_commands]

        full_commands = [
            "ui_print(\"\");",
            "ui_print(\"======== Auto Generated By MTK PORT TOOL ========\");",
            f"ui_print(\"- Author: {author}\");",
            f"ui_print(\"- Version: {version}\");",
            f"ui_print(\"- MTK PORT TOOL Info below:\");",
            f"ui_print(\"    TOOL Author: {tool_author}\");",
            f"ui_print(\"    TOOL Version: {tool_version}\");",
            f"ui_print(\"{'=' * 49}\");",
            # unmount before flash
            f"ifelse(is_mounted(\"/system\"), unmount(\"/system\"));",
            # format system
            f"run_program(\"mke2fs\", \"{partitions['system']}\");",
            f"format(\"ext4\", \"EMMC\", \"/dev/block/mmcblk0p4\", \"0\", \"/system\");",
            "set_progress(0.1);",
            # mount system -> /system
            "ui_print(\"- Mounting system partition...\");",
            f"mount(\"ext4\", \"EMMC\", \"{partitions['system']}\", \"/system\", \"max_batch_time=0,commit=1,data=ordered,barrier=1,errors=panic,nodelalloc\");",
            # extract system -> /system
            "ui_print(\"- Extract system conditionally...\");",
            "set_progress(0.2);",
            "package_extract_dir(\"system\", \"/system\");",
            "set_progress(0.5);",
            # create symlinks and setup metadata
            "ui_print(\"- Create symlinks and setup metadata...\");",
            *updater_script_content,
            "set_progress(0.8);",
            "ui_print(\"- Flash boot image...\");",
            f"package_extract_file(\"boot.img\", \"{partitions['boot']}\");",
            "set_progress(0.9);",
            "ui_print(\"- Done!\");",
            # every thing done, now unmount system
            "unmount(\"/system\");",
            "set_progress(1);",
        ]
        return "\n".join(full_commands)


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
        print(getcwd())
        with open("bootinfo.txt", encoding='ascii') as f:
            (
                base,
                ramdisk_addr,
                second_addr,
                tags_addr,
                page_size,
                name,
                cmdline,
                padding_size,
            ) = [i.lstrip("\x00").rstrip().split(':')[1] for i in iter(f.readline, "")]
        repack_bootimg(base, cmdline, page_size, padding_size, None)
        chdir(self.retcwd)

    def __entry__(self):
        return self

    def __exit__(self, *vars):
        chdir(self.retcwd)


class portutils:
    def __init__(self, items: dict, bootimg: str, sysimg: str, portzip: str, genimg: bool = False, stdlog=None):
        self.items = items
        self.sysimg = sysimg
        self.bootimg = bootimg
        self.portzip = portzip
        self.genimg = genimg  # if you want system.img
        self.outdir = Path("out")
        if not self.outdir.exists():
            self.outdir.mkdir(parents=True)
        if not stdlog:
            self.std = stdout
        else:
            self.std = stdlog
        if not self.__check_exist:
            print("文件是否存在检查不通过", file=self.std)
            return

        # sdat
        self.sdat = False

    @property
    def __check_exist(self) -> bool:
        for i in (self.sysimg, self.bootimg, self.portzip):
            if not Path(i).exists():
                return False
        return True

    def execv(self, cmd, verbose=False):
        if verbose:
            print("执行命令：\n", *cmd if type(cmd) == list else cmd, file=self.std)
        creationflags = subprocess.CREATE_NO_WINDOW if osname == 'nt' else 0
        try:
            ret = subprocess.run(cmd,
                                 shell=False,
                                 # stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 creationflags=creationflags
                                 )
        except:
            self.std.write("! Cannot execute program\n")
            return -1
        if verbose:
            print("结果返回：\n", ret.stdout.decode('utf-8', errors='ignore'), file=self.std)
        return ret.returncode

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
            return dest.write_bytes(src.read_bytes())

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
        # port.write_bytes(Path("tmp/rom/boot.img").read_bytes())

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
                            __replace(basedir.joinpath(i), portdir.joinpath(i).absolute())
                case 'replace_fstab':
                    for i in self.items['replace']['fstab']:
                        if basedir.joinpath(i).exists():
                            print(f"替换分区表 {i}", file=self.std)
                            __replace(basedir.joinpath(i), portdir.joinpath(i).absolute())
                case 'selinux_permissive':
                    if portdir.joinpath("bootinfo.txt").exists():
                        with portdir.joinpath("bootinfo.txt").open("r+") as f:
                            lines = [i.rstrip() for i in f.readlines()]
                            # f.truncate(0)
                            flag = False
                            for i in lines:
                                if "androidboot.selinux=permissive" in i:
                                    print("已开启selinux宽容，无需操作", file=self.std)
                                    flag = True
                            if flag:
                                continue
                            else:
                                f.truncate(0)
                                for i in lines:
                                    if i.startswith("cmdline:"):
                                        print("开启selinux宽容", file=self.std)
                                        f.write(i + " androidboot.selinux=permissive\n")
                                    else:
                                        f.write(i + '\n')
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
        __replace(outboot, to)
        # patch with magisk
        if self.items.get("patch_magisk"):
            if op.isfile(self.items.get("magisk_apk")):
                parseMagiskApk(self.items['magisk_apk'], self.items['target_arch'], self.std)
                bp = BootPatcher(magiskboot_bin, legacysar=True, progress=None, log=self.std)
                if not bp.patch(str(to)):
                    bp.cleanup()
                else:
                    __replace(Path("new-boot.img"), to)
                    unlink("new-boot.img")

            else:
                print(f"找不到{self.items['magisk_apk']}", file=self.std)

        return True

    def __port_system(self):
        def __replace(val: str):
            print(f"替换$base/{val} -> $port/{val}...", file=self.std)
            if "*" in val:  # 匹配通配符
                for file in glob.glob(op.join(str(base_prefix), val)):
                    relfile = op.relpath(file, str(base_prefix))
                    print(f"\t$base/{relfile} -> $port/{relfile}", file=self.std)
                    port_prefix.joinpath(relfile).write_bytes(
                        base_prefix.joinpath(relfile).read_bytes()
                    )
            elif base_prefix.joinpath(val).is_dir():
                if port_prefix.joinpath(val).exists():
                    rmtree(port_prefix.joinpath(val))
                copytree(base_prefix.joinpath(val),
                         port_prefix.joinpath(val))
            else:
                port_prefix.joinpath(val).write_bytes(
                    base_prefix.joinpath(val).read_bytes()
                )

        unpack_flag = False
        print("检测system md5检验和是否相同", file=self.std)
        with open(self.sysimg, 'rb') as f:
            md5filter = md5()
            for chunk in iter(lambda: f.read(4096), b""):
                md5filter.update(chunk)
            sysmd5 = md5filter.hexdigest()
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
            unpack_flag = False
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

        if Path("tmp/rom/system.new.dat").exists():
            print("检测到system.new.dat格式镜像，需要转换", file=self.std)
            self.sdat = True
            with open("tmp/rom/system.transfer.list") as t:
                self.sdat_ver = int(t.readline().rstrip("\n"))
            sdat2img("tmp/rom/system.transfer.list", "tmp/rom/system.new.dat", "tmp/rom/system.img")
            print("解包目标system镜像中...", file=self.std)
            Extractor().main("tmp/rom/system.img", "tmp/rom/system")

        base_prefix = Path("base/system")
        port_prefix = Path("tmp/rom/system")
        for item in self.items['flags']:
            item_flag = self.items[item]
            if not item_flag: continue
            if item == 'replace_kernel' or item == 'replace_fstab':
                continue
            if item.startswith("replace_"):
                for i in self.items['replace'][item.split('_')[1]]:
                    if base_prefix.joinpath(i).exists() or ("*" in i):
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
            item_flag = self.items['flags'][item]
            if not item_flag: continue
            match item:
                case 'use_custom_update-binary':
                    print("使用提供的update-binary以解决在twrp刷入报错的问题", file=self.std)
                    Path("tmp/rom/META-INF/com/google/android/update-binary").write_bytes(
                        Path("bin/update-binary").read_bytes())
                case 'generate_script':
                    print("自动重新生成刷机脚本解决一些莫名奇妙的问题...", file=self.std)
                    if (not self.sdat) or (len(self.items['partitions']) != 0):
                        updater = Path("tmp/rom/META-INF/com/google/android/updater-script")
                        if updater.exists():
                            with updater.open('r+', encoding='utf-8', newline='\n') as f:
                                # try to get author
                                author = self.items.get('author')
                                version = self.items.get('version')
                                if not author: author = tool_author
                                if not version: version = tool_version
                                new_script = updaterutil(f).generate(author, version, self.items['partitions'])
                                if new_script:
                                    f.seek(0, 0)
                                    f.truncate()
                                    f.write(new_script)
                                    print("脚本生成成功...", file=self.std)
                                else:
                                    print("脚本生成错误...", file=self.std)
                        else:
                            print("刷机脚本未找到...", file=self.std)
                    else:
                        print("刷机包可能是sdat格式或者你的partitions里没指定system和boot", file=self.std)
        print("打包卡刷包.....", end='', file=self.std)
        outpath = Path(f"out/{op.basename(self.portzip)}")
        if outpath.exists():
            outpath.unlink()

        if self.sdat:
            print("sdat格式打包...", file=self.std)
            print("生成system镜像中...", file=self.std)
            config_dir = Path("tmp/rom/config")
            # if config_dir.exists():
            #    rmtree(config_dir)
            # config_dir.mkdir(parents=True)

            # 去重
            with config_dir.joinpath("system_file_contexts").open('r+') as fc:
                fc_info = [i.rstrip() for i in iter(fc.readline, "")]
                new_fc_info = []
                for i in fc_info:
                    if not i in new_fc_info:
                        new_fc_info.append(i)
                fc.seek(0, 0)
                fc.truncate(0)
                fc.write("\n".join(new_fc_info))

            fs_label = []
            fs_label.append(
                ["/", '0', '0', '0755'])
            fs_label.append(
                ["/lost\\+found", '0', '0', '0700'])
            print("添加缺失的文件和权限", file=self.std)
            fs_files = [i[0] for i in fs_label]
            for root, dirs, files in walk("tmp/rom/system"):
                if "tmp/install" in root.replace('\\', '/'): continue  # skip lineage spec
                for dir in dirs:
                    unix_path = op.join(
                        op.join("/system", op.relpath(op.join(root, dir), "tmp/rom/system")).replace("\\", "/")
                    ).replace("[", "\\[")
                    if not unix_path in fs_files:
                        fs_label.append([unix_path.lstrip('/'), '0', '0', '0755'])
                for file in files:
                    unix_path = op.join(
                        op.join("/system", op.relpath(op.join(root, file), "tmp/rom/system")).replace("\\", "/")
                    ).replace("[", "\\[")
                    if not unix_path in fs_files:
                        link = self.__readlink(op.join(root, file))
                        if link:
                            fs_label.append(
                                [unix_path.lstrip('/'), '0', '2000', '0755', link])
                        else:
                            if "bin/" in unix_path:
                                mode = '0755'
                            else:
                                mode = '0644'
                            fs_label.append(
                                [unix_path.lstrip('/'), '0', '2000', mode])
            fs_config = config_dir.joinpath("system_fs_config").open('w', newline='\n')
            fs_label.sort()
            for fs in fs_label:
                fs_config.write(" ".join(fs) + '\n')
            fs_config.close()

            fit_size = self.__pack_fit_size()
            sys_size = stat(self.sysimg).st_size

            make_ext4fs_cmd = [
                make_ext4fs_bin,
                '-s',  # sparse image
                '-J',  # has journal
                '-T', '1',  # custom mtime
                '-l', f'{sys_size if sys_size >= fit_size else fit_size}',  # pack size
                '-C', f"{str(config_dir.joinpath('system_fs_config'))}",
                '-S', f"{str(config_dir.joinpath('system_file_contexts'))}",
                '-L', 'system', '-a', 'system',
                "out/system_raw.img", "tmp/rom/system",
            ]
            self.execv(make_ext4fs_cmd, verbose=True)

            # convert to simg
            self.execv([img2simg_bin, "out/system_raw.img", "out/system.img"])

            if op.isdir("tmp/rom/system"):
                rmtree("tmp/rom/system")
            if op.isdir("tmp/rom/config"):
                rmtree("tmp/rom/config")
            if op.isfile("tmp/rom/system.transfer.list"):
                unlink("tmp/rom/system.transfer.list")

            img2sdat("out/system.img", "tmp/rom", self.sdat_ver)
            if op.isfile("tmp/rom/system.img"):
                print("删除遗留system镜像...", file=self.std)
                unlink("tmp/rom/system.img")
        ziputil.compress(str(outpath), "tmp/rom/")
        print("完成！", file=self.std)
        return

    def __pack_fit_size(self):
        total = 0
        for root, dirs, files in walk("tmp/rom/system"):
            for file in files:
                total += stat(op.join(root, file)).st_size
        return total * 1.2

    def __readlink(self, dest: str):
        if osname == 'nt':
            with open(dest, 'rb') as f:
                if f.read(10) == b'!<symlink>':
                    return f.read().decode('utf-16').rstrip('\0')
                else:
                    return None
        else:
            try:
                readlink(dest)
            except:
                return None

    def __pack_img(self):
        def __symlink(src: str, dest: str):
            def setSystemAttrib(path: str) -> wintypes.BOOL:
                return windll.kernel32.SetFileAttributesA(path.encode('gb2312'), wintypes.DWORD(0x4))

            print(f"创建软链接 [{src}] -> [{dest}]", file=self.std)
            pdest = Path(dest)
            if not pdest.parent.exists():
                pdest.parent.mkdir(parents=True)
            if osname == 'nt':
                with open(dest, 'wb') as f:
                    f.write(
                        b"!<symlink>" + src.encode('utf-16') + b'\0\0')
                setSystemAttrib(dest)
            else:
                symlink(src, dest)

        print("将输出打包为system镜像", file=self.std)
        updater = Path("tmp/rom/META-INF/com/google/android/updater-script")
        config_dir = Path("tmp/config")
        if config_dir.exists():
            rmtree(config_dir)
        config_dir.mkdir(parents=True)

        fs_label = []
        fc_label = []
        fs_label.append(
            ["/", '0', '0', '0755'])
        fs_label.append(
            ["/lost\\+found", '0', '0', '0700'])
        fc_label.append(
            ['/', 'u:object_r:system_file:s0'])
        fc_label.append(
            ['/system(/.*)?', 'u:object_r:system_file:s0'])
        if not updater.exists():
            self.std.write(f"Error: 刷机脚本不存在")
            return

        print("分析刷机脚本...", file=self.std)
        contents = updaterutil(updater.open('r', encoding='utf-8')).content
        romprefix = Path("tmp/rom/")
        last_fpath = ''
        for content in contents:
            command, *args = content
            match command:
                case 'symlink':
                    src, *targets = args
                    for target in targets:
                        __symlink(src, str(romprefix.joinpath(target.lstrip('/'))))
                case 'set_metadata' | 'set_metadata_recursive':
                    dirmode = False if command == 'set_metadata' else True
                    fpath, *fargs = args

                    fpath = fpath.replace("+", "\\+").replace("[", "\\[").replace('//', '/')
                    if fpath == last_fpath: continue  # skip same path
                    # initial
                    uid, gid, mode, extra = '0', '0', '644', ''
                    selable = 'u:object_r:system_file:s0'  # common system selable
                    for index, farg in enumerate(fargs):
                        match farg:
                            case 'uid':
                                uid = fargs[index + 1]
                            case 'gid':
                                gid = fargs[index + 1]
                            case 'mode' | 'fmode' | 'dmode':
                                if dirmode and farg == 'dmode':
                                    mode = fargs[index + 1]
                                else:
                                    mode = fargs[index + 1]
                            case 'capabilities':
                                # continue
                                if fargs[index + 1] == '0x0':
                                    extra = ''
                                else:
                                    extra = 'capabilities=' + fargs[index + 1]
                            case 'selabel':
                                selable = fargs[index + 1]
                    fs_label.append(
                        [fpath.lstrip('/'), uid, gid, mode, extra])
                    fc_label.append(
                        [fpath, selable])
                    last_fpath = fpath

        # Patch fs_config
        print("添加缺失的文件和权限", file=self.std)
        fs_files = [i[0] for i in fs_label]
        for root, dirs, files in walk("tmp/rom/system"):
            if "tmp/install" in root.replace('\\', '/'): continue  # skip lineage spec
            for dir in dirs:
                unix_path = op.join(
                    op.join("/system", op.relpath(op.join(root, dir), "tmp/rom/system")).replace("\\", "/")
                ).replace("[", "\\[")
                if not unix_path in fs_files:
                    fs_label.append([unix_path.lstrip('/'), '0', '0', '0755'])
            for file in files:
                unix_path = op.join(
                    op.join("/system", op.relpath(op.join(root, file), "tmp/rom/system")).replace("\\", "/")
                ).replace("[", "\\[")
                if not unix_path in fs_files:
                    link = self.__readlink(op.join(root, file))
                    if link:
                        fs_label.append(
                            [unix_path.lstrip('/'), '0', '2000', '0755', link])
                    else:
                        if "bin/" in unix_path:
                            mode = '0755'
                        else:
                            mode = '0644'
                        fs_label.append(
                            [unix_path.lstrip('/'), '0', '2000', mode])

        # generate config
        print("生成fs_config 和 file_contexts", file=self.std)
        fs_config = config_dir.joinpath("system_fs_config").open('w', newline='\n')
        file_contexts = config_dir.joinpath("system_file_contexts").open('w', newline='\n')
        fs_label.sort();
        fc_label.sort()
        for fs in fs_label:
            fs_config.write(" ".join(fs) + '\n')
        for fc in fc_label:
            file_contexts.write(" ".join(fc) + '\n')
        fs_config.close()
        file_contexts.close()

        fit_size = self.__pack_fit_size()
        sys_size = stat(self.sysimg).st_size
        make_ext4fs_cmd = [
            make_ext4fs_bin,
            # '-s', # sparse image
            '-J',  # has journal
            '-T', '1',  # custom mtime
            '-l', f'{sys_size if sys_size >= fit_size else fit_size}',  # pack size
            '-C', f"{str(config_dir.joinpath('system_fs_config'))}",
            '-S', f"{str(config_dir.joinpath('system_file_contexts'))}",
            '-L', 'system', '-a', 'system',
            "out/system.img", "tmp/rom/system",
        ]
        self.execv(make_ext4fs_cmd, verbose=True)
        Path("out/boot.img").write_bytes(Path("tmp/rom/boot.img").read_bytes())
        print("打包完成！\n"
              "boot输出到[out/boot.img]\n"
              "system输出到[out/system.img]", file=self.std)
        self.clean()
        return

    def start(self):
        self.__decompress_portzip()
        self.__port_boot()
        self.__port_system()
        if self.genimg:
            self.__pack_img()
        else:
            self.__pack_rom()

    def clean(self):
        print("移植完成，清理目录", file=self.std)
        if Path("tmp").exists():
            rmtree("tmp")
