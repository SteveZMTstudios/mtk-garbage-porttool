# configs for porttool
support_chipset_portstep = {
    'mt6572/mt6582/mt6592 kernel-3.4.67': {
        'kernel_only': False,
        'flags': { # flag control in item
            'replace_kernel': True, # startwith replace will replace file
            'replace_fstab': False,
            'selinux_permissive': True,
            'enable_adb': True,
            # ========== split line ============ ↑ is boot.img ↓ is system
            'replace_firmware': True,
            'replace_mddb': True,
            'replace_malidriver': True,
            'replace_audiodriver': False,
            'replace_libshowlogo': False,
            'replace_mtk-kpd': True,
            'replace_gralloc': True,
            'replace_hwcomposer': True,
            'replace_ril': False,
            'single_simcard': False,
            'dual_simcard': False,
            'fit_density': True,
            'change_model': True,
            'change_timezone': True,
            'change_locale': True,
            'use_custom_update-binary': True,
        },
        'replace': { # if you flags startswith replace_ you must define which files need to be replace
            'kernel': [ # boot from base -> port
                "kernel"
            ],
            'fstab': [  # boot from base -> port
                "initrd/fstab",
                "initrd/fstab.mt6572",
                "initrd/fstab.mt6582",
                "initrd/fstab.mt6592",
            ],
            'firmware': [ # below is system
                "etc/firmware" # if is a directory, will remove first
            ],
            'mddb': [
                "etc/mddb"
            ],
            'malidriver': [
                "lib/libMali.so"
            ],
            'audiodriver': [
                "lib/libaudio.primary.default.so",
                "etc/audio_effects.conf",
                "etc/audio_policy.conf"
            ],
            'libshowlogo': [
                "lib/libshowlogo.so"
            ],
            'mtk-kpd': [
                "usr/keylayout/mtk-kpd.kl"
            ],
            'ril': [
                "bin/ccci_fsd",
                "bin/ccci_mdinit",
                "bin/gsm0710muxd",
                "bin/gsm0710muxdmd2 ",
                "bin/rild",
                "bin/rildmd2",
                "lib/librilmtk.so",
                "lib/librilmtkmd2.so",
                "lib/librilutils.so ",
                "lib/mtk-ril.so",
                "lib/mtk-rilmd2.so",
            ],
            'gralloc': [
                "lib/hw/gralloc.mt6572.so",
                "lib/hw/gralloc.mt6582.so",
                "lib/hw/gralloc.mt6592.so",
            ],
            'hwcomposer': [
                "lib/hw/hwcomposer.mt6572.so",
                "lib/hw/hwcomposer.mt6582.so",
                "lib/hw/hwcomposer.mt6592.so",
            ]
        },
    },
    'kernel only (only replace kernel)': {
        'kernel_only': True,
        'flags': {
            'replace_kernel': True,
            'selinux_permissive': True,
            'enable_adb': True,
            'replace_firmware': True,
            'replace_mddb': True,
        },
        'replace': {
            'kernel': [ # boot from base -> port
                "kernel"
            ],
            'firmware': [ # below is system
                "etc/firmware" # if is a directory, will remove first
            ],
            'mddb': [
                "etc/mddb"
            ],
        },
    },
}
support_chipset = list(support_chipset_portstep.keys())
support_packtype = [
    'zip', 'img'
]