#!/usr/bin/env python
# -*- coding: utf-8 -*-


from __future__ import print_function

import os
import tempfile

from . import blockimgdiff, sparse_img


def main(INPUT_IMAGE, OUT_DIR='.', VERSION=None, PREFIX='system'):
    print('img2sdat binary - version: 1.7\n')

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    # Generate output files
    blockimgdiff.BlockImageDiff(sparse_img.SparseImage(INPUT_IMAGE, tempfile.mkstemp()[1], '0'), None, VERSION).Compute(
        OUT_DIR + '/' + PREFIX)

    print('Done! Output files: %s' % os.path.dirname(OUT_DIR + '/' + PREFIX))
