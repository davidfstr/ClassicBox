"""
Functions for manipulating "box" directories, which are self-contained
virtual machines.
"""

import os


def box_create(box_dirpath):
    """
    Creates an empty box at the specified path.
    """
    os.mkdir(box_dirpath)
    os.mkdir(os.path.join(box_dirpath, 'bin'))
    os.mkdir(os.path.join(box_dirpath, 'etc'))
    os.mkdir(os.path.join(box_dirpath, 'mount'))
    os.mkdir(os.path.join(box_dirpath, 'mount-disabled'))
    os.mkdir(os.path.join(box_dirpath, 'rom'))
    os.mkdir(os.path.join(box_dirpath, 'share'))