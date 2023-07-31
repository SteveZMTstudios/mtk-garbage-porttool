import os.path as op

# init
bin_dir = op.join(op.dirname(__file__), "bin")
support_chipset = [
    'mt6572/mt6582/mt6592 kernel-3.4.67',
    'mt6735(m)/mt6737(m) kernel-3.18.22',
    'mt6580(m) kernel-3.18.22',
]
support_packtype = [
    'zip', 'img'
]