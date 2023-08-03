# configs for porttool
support_chipset_portstep = {
    'mt6572/mt6582/mt6592 kernel-3.4.67': {
        'kernel_only': False,
        'flags': { # flag control in item
            'replace_kernel': True, # startwith replace will replace file
            'replace_fstab': False,
            'selinux_permissive': True,
            'enable_adb': True,
            'replace_firmware': True,
            'replace_mddb': True,
            'replace_malidriver': True,
            'replace_audiodriver': False,
            'single_simcard': False, # else will follow else rules
            'dual_simcard': False,
        },
        'replace': {
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
        },
    },
    'kernel only (only replace kernel)': {
        'kernel_only': True,
        'flags': {
            'replace_kernel': True,
            'replace_firmware': True,
            'selinux_permissive': True,
            'enable_adb': True,
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