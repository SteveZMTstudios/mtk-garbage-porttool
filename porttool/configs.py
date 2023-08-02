# configs for porttool
support_chipset_portstep = {
    'mt6572/mt6582/mt6592 kernel-3.4.67': {
        'kernel_only': False,
        'flags': {
            'replace_kernel': True,
            'replace_fstab': False,
            'replace_firmware': True,
            'replace_density': True,
            'replace_modelname': True,
            'single_simcard': False,
            'dual_simcard': False,
        },
        'replace': {
            'common': [
                "etc/firmware",
                "etc/mddb"
            ],
        'bugfix': {
            'audio': [
                "lib/libaudio.primary.default.so"
            ]
        }
        },
    },
    'kernel only (only replace kernel)': {
        'kernel_only': True,
    }
}
support_chipset = support_chipset_portstep.keys()
support_packtype = [
    'zip', 'img'
]