"""
Functions to manipulate and examine disk images.
"""


_DISK_IMAGE_EXTENSIONS = [
    '.dsk', '.hfv', # Raw disk image
    '.toast',       # Toast disk image
    '.iso', '.cdr', # ISO disk image
    '.dmg',         # UDIF disk image
    '.img',         # NDIF disk image (Disk Copy 6.3)
]

_MVM_DISK_IMAGE_EXTENSIONS = [
    '.dsk', '.hfv', # Raw disk image
    # TODO: Check whether other disk image formats are
    #       supported by Mini vMac.
    #       (Basilisk and SheepShaver support a TON of formats.)
]

_BASILISK_DISK_IMAGE_EXTENSIONS = [
    '.dsk', '.hfv', # Raw disk image
    '.toast',       # Toast disk image
    '.iso', '.cdr', # ISO disk image
    
    # NOTE: Basilisk doesn't seem to consistently be able mount .img and .dmg correctly.
    #       Workaround on OS X by converting it to a .dsk using the `dd` tool.
    #       [TODO: Inspect the Basilisk source to see if it attempts to support UDIF/NDIF images.]
    #'.dmg',         # UDIF disk image
    #'.img',         # NDIF disk image (Disk Copy 6.3)
]


def is_disk_image(filename):
    """
    Returns whether the specified file is a disk image.
    """
    return _filename_has_extension_in_list(filename, _DISK_IMAGE_EXTENSIONS)


def is_mini_vmac_supported_disk_image(filename):
    """
    Returns whether the specified file is a disk image that can be mounted by
    Mini vMac.
    """
    return _filename_has_extension_in_list(filename, _MVM_DISK_IMAGE_EXTENSIONS)


def is_basilisk_supported_disk_image(filename):
    """
    Returns whether the specified file is a disk image that can be mounted by
    Basilisk II. In general, any such image can also be mounted by SheepShaver.
    """
    return _filename_has_extension_in_list(filename, _BASILISK_DISK_IMAGE_EXTENSIONS)


def _filename_has_extension_in_list(filename, extensions):
    filename = filename.lower()
    for ext in extensions:
        if filename.endswith(ext):
            return True
    return False
