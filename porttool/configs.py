# configs for porttool
support_chipset_portstep = {
    'mt6572/mt6582/mt6592 kernel-3.4.67': {
        'kernel_only': False,
        'flags': { # flag control in item
            'replace_kernel': True, # startwith replace will replace file
            'replace_fstab': False,
            'replace_firmware': True,
            'replace_mddb': True,
            'replace_malidriver': True,
            'replace_audiodriver': False,
            'single_simcard': False, # else will follow else rules
            'dual_simcard': False,
        },
        'replace': {
            'kernel': [ # boot from base -> port
                "split_img/boot.img-kernel"
            ],
            'fstab': [  # boot from base -> port
                "ramdisk/fstab",
                "ramdisk/fstab.mt6572",
                "ramdisk/fstab.mt6582",
                "ramdisk/fstab.mt6592",
            ],
            'firmware': [ # below is system
                "etc/firmware" # if is a directory, will remove first
            ],
            'firmware': [
                "etc/mddb"
            ],
            'malidriver': [
                "lib/libMali.so"
            ],
            'audiodriver': [
                "lib/libaudio.primary.default.so"
            ],
        },
    },
    'kernel only (only replace kernel)': {
        'kernel_only': True,
        'flags': {},
    }
}
support_chipset = list(support_chipset_portstep.keys())
print(support_chipset)
support_packtype = [
    'zip', 'img'
]