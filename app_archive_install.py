#!/usr/bin/env python

"""
Automatically installs an app from an archive file.

Syntax:
    app_archive_install.py <box directory> <archive file>
"""

# TODO: Extract common functionality to classicbox.box
import box_up

# TODO: Extract common functionality to classicbox.catalog
from catalog_create import create_catalog
from catalog_diff import create_catalog_diff
from catalog_diff import DirectoryDiff
from catalog_diff import EMPTY_DIFF
from catalog_diff import FileDiff
from catalog_diff import print_catalog_diff
from catalog_diff import remove_ignored_parts_from_catalog_diff

from classicbox.alias.file import create_alias_file
from classicbox.archive import archive_extract
from classicbox.disk import is_basilisk_supported_disk_image
from classicbox.disk import is_disk_image
from classicbox.disk.hfs import hfs_delete
from classicbox.disk.hfs import hfs_exists
from classicbox.disk.hfs import hfs_ls
from classicbox.disk.hfs import hfs_mount
from classicbox.disk.hfs import hfs_stat
from contextlib import contextmanager
import os
import os.path
import sys
from tempfile import NamedTemporaryFile


RECOGNIZED_INSTALLER_APP_CREATORS = [
    'STi0',         # Stuffit InstallerMaker
    'bbkr',         # Apple Installer
    'VIS3',         # InstallerVISE
    'EXTR',         # CompactPro AutoExtractor Self-Extracting Archive
]

OS_7_5_3_IGNORE_TREE = [
    ["System Folder", [
        ["Apple Menu Items", [
            "Recent Applications"
        ]],
        ["Control Panels", [
            "Apple Menu Options",
            "MacTCP"
        ]],
        ["Extensions", [
            "Printer Share"
        ]],
        "MacTCP DNR",
        ["Preferences", [
            "ASLM Preferences",
            "Apple Menu Options Prefs",
            "Finder Preferences",
            "Macintosh Easy Open Preferences",
            "Users & Groups Data File",
            "WindowShade Preferences"
        ]]
    ]]
]


VERBOSE_CATALOG_DIFF = True

def main(args):
    # Parse arguments
    (box_dirpath, archive_filepath) = args
    
    # Extract the archive
    with archive_extract(archive_filepath) as archive:
        contents_dirpath = archive.extraction_dirpath
        
        # TODO: Probably will need to be smarter here for archives
        #       that expand with a single directory at the root
        
        # Locate disk images in archive, if any
        disk_image_filepaths = []
        for filename in os.listdir(contents_dirpath):
            if is_disk_image(filename):
                disk_image_filepaths.append(os.path.join(contents_dirpath, filename))
        
        # Identify the primary disk image
        if len(disk_image_filepaths) == 0:
            # TODO: ...
            raise NotImplementedError('Did not find any disk images in archive. Not sure what to do.')
            
        elif len(disk_image_filepaths) == 1:
            primary_disk_image_filepath = disk_image_filepaths[0]
            
        elif len(disk_image_filepaths) >= 2:
            choice = choose_from_menu(
                'Found multiple disk images in archive.',
                'Please choose the primary disk image containing the program or installer:',
                [os.path.basename(path) for path in disk_image_filepaths] + [
                    '<Cancel>'])
            
            if choice == len(disk_image_filepaths):
                # Cancel
                return
            else:
                primary_disk_image_filepath = disk_image_filepaths[choice]
        
        # Open the primary disk image
        hfs_mount(primary_disk_image_filepath)
        
        # List the root items
        root_items = hfs_ls()
        
        # Look for installer apps
        installer_app_items = []
        app_creators = []
        for item in root_items:
            if item.type == 'APPL':
                app_creators.append(item.creator)
                
                if item.creator in RECOGNIZED_INSTALLER_APP_CREATORS:
                    installer_app_items.append(item)
        
        # Identify the primary installer app
        if len(installer_app_items) == 0:
            if len(app_creators) == 0:
                details = 'Did not find any applications.'
            else:
                details = 'However applications of type %s were found.' % \
                    repr(app_creators)
            
            # TODO: Continue looking for the designated app...
            raise NotImplementedError(
                ('Did not find any installer applications. %s ' +
                 'Not sure what to do.') % details)
            
        elif len(installer_app_items) == 1:
            primary_installer_app_item = installer_app_items[0]
            
        elif len(installer_app_items) >= 2:
            choice = choose_from_menu(
                'Found multiple installer applications.',
                'Please choose the primary installer for this program:',
                [item.name for item in installer_app_items] + ['<Cancel>'])
            
            if choice == len(installer_app_items):
                # Cancel
                return
            else:
                primary_installer_app_item = installer_app_items[choice]
        
        # Temporarily mount the disk images inside the VM
        with mount_disk_images_temporarily(box_dirpath, disk_image_filepaths):
            
            # Set the installer app as the boot app
            set_boot_app_of_box(
                box_dirpath,
                primary_disk_image_filepath,
                [primary_installer_app_item.name])
            
            while True:
                # Remember state of boot volume prior to installation
                boot_disk_image_filepath = locate_boot_volume_of_box(box_dirpath)
                preinstall_catalog = create_catalog(boot_disk_image_filepath)
                
                # Boot the box and wait for the user to install the app
                run_box(box_dirpath)
                
                # Detect changes on the boot volume since installation
                postinstall_catalog = create_catalog(boot_disk_image_filepath)
                install_diff = create_catalog_diff(preinstall_catalog, postinstall_catalog)
                remove_ignored_parts_from_catalog_diff(
                    install_diff,
                    OS_7_5_3_IGNORE_TREE)
                
                # If the user didn't appear to install anything,
                # provide the option to try again
                if install_diff == EMPTY_DIFF:
                    choice = choose_from_menu(
                        None,
                        "It appears you didn't install anything.",
                        ['Try Again', 'Cancel'])
                    
                    if choice == 0: # Try Again
                        continue
                    else:           # Cancel
                        return
                
                if VERBOSE_CATALOG_DIFF:
                    print_catalog_diff(install_diff)
                    print
                
                # Look for the installed app
                installed_apps = []
                for (item, itempath_components) in \
                        walk_added_files_in_catalog_diff(
                            install_diff, boot_disk_image_filepath):
                    if item.type == 'APPL':
                        installed_apps.append(itempath_components)
                
                if len(installed_apps) == 0:
                    # TODO: Offer to run the installer again or cancel
                    raise NotImplementedError(
                        'No applications found in the installed items. ' +
                        'Not sure what to do.')
                elif len(installed_apps) == 1:
                    installed_app_filepath_components = installed_apps[0]
                elif len(installed_apps) >= 2:
                    choice = choose_from_menu(
                        'Multiple applications were installed.',
                        'Please choose the primary application:',
                        [components[-1] for components in installed_apps] + \
                            ['<Cancel>'])
                    
                    if choice == len(installed_apps):
                        # Cancel
                        return
                    else:
                        installed_app_filepath_components = \
                            installed_apps[choice]
                
                # (Found the installed app)
                break
            
            # (Unmount the archive's disk images since installation is done)
        
        # (Close the archive since installation is done)
    
    # Set the installed app as the boot app
    set_boot_app_of_box(
        box_dirpath,
        boot_disk_image_filepath,
        installed_app_filepath_components)


def choose_from_menu(prompt, subprompt, menuitems):
    if prompt is not None:
        print prompt
        print
    
    while True:
        print subprompt
        i = 1
        for item in menuitems:
            print '    %d: %s' % (i, item); i += 1
        try:
            choice = int(raw_input('Choice? '))
            if 1 <= choice < i:
                break
            else:
                raise ValueError
        except ValueError:
            print 'Not a valid choice.'
            continue
        finally:
            print
    
    return choice - 1


@contextmanager
def mount_disk_images_temporarily(box_dirpath, disk_image_filepaths):
    for x in _mdit_helper(box_dirpath, 0, disk_image_filepaths):
        yield


def _mdit_helper(box_dirpath, i, disk_image_filepaths):
    if i == len(disk_image_filepaths):
        yield
        return
    disk_image_filepath = disk_image_filepaths[i]
    
    mount_dirpath = os.path.join(box_dirpath, 'mount')
    disk_image_ext = os.path.splitext(disk_image_filepath)[1]
    link_filepath = _mktemp_dammit(dir=mount_dirpath, suffix=disk_image_ext)
    
    # NOTE: os.symlink() is not available on Windows.
    #       The underlying emulators support Windows .lnk files, so those should
    #       be created on Windows systems. Be sure to test box_up() when such
    #       links are present.
    os.symlink(disk_image_filepath, link_filepath)
    try:
        for x in _mdit_helper(box_dirpath, i+1, disk_image_filepaths):
            yield
    finally:
        os.remove(link_filepath)


def _mktemp_dammit(*args, **kwargs):
    """
    Same as tempfile.mktemp(), but isn't a deprecated function.
    
    Note that this function is vulnerable to symlink attacks.
    Recommended only when `dir` is specified explicitly.
    """
    with NamedTemporaryFile(*args, delete=False, **kwargs) as file:
        pass
    
    temp_filepath = file.name
    os.remove(temp_filepath)
    return temp_filepath


def walk_added_files_in_catalog_diff(diff, disk_image_filepath):
    for x in _walk_added_files_in_diff(diff, disk_image_filepath, ()):
        yield x

def _walk_added_files_in_diff(
        diff, disk_image_filepath, parent_dirpath_components):
    
    for add in diff.adds:
        for x in walk_files(
                disk_image_filepath,
                parent_dirpath_components + (add,)):
            yield x
    
    for edit in diff.edits:
        if isinstance(edit, FileDiff):
            edit_itempath_components = (parent_dirpath_components + (edit.name,))
            edit_item = hfs2_stat(disk_image_filepath, edit_itempath_components)
            yield (edit_item, edit_itempath_components)
        elif isinstance(edit, DirectoryDiff):
            for x in _walk_added_files_in_diff(
                    edit.listing_diff,
                    disk_image_filepath,
                    parent_dirpath_components + (edit.name,)):
                yield x
        else:
            raise ValueError


def walk_files(disk_image_filepath, top_itempath_components):
    top_item = hfs2_stat(disk_image_filepath, top_itempath_components)
    if top_item.is_file:
        yield (top_item, top_itempath_components)
    else:
        for x in _walk_files_in_directory(
                disk_image_filepath, top_itempath_components):
            yield x


def _walk_files_in_directory(disk_image_filepath, parent_dirpath_components):
    for item in hfs2_ls(disk_image_filepath, parent_dirpath_components):
        if item.is_file:
            yield (item, parent_dirpath_components + (item.name,))
        else:
            for x in _walk_files_in_directory(
                    disk_image_filepath,
                    parent_dirpath_components + (item.name,)):
                yield x

# ------------------------------------------------------------------------------

def set_boot_app_of_box(box_dirpath, disk_image_filepath, app_filepath_components):
    install_autoquit_in_box(box_dirpath)
    set_autoquit_app(box_dirpath, disk_image_filepath, app_filepath_components)

#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# install_autoquit_in_box

def install_autoquit_in_box(box_dirpath):
    # Check whether already installed
    if is_autoquit_in_box(box_dirpath):
        return
    
    # NOTE: I can delay implementing this by cheating and installing AutQuit7
    #       manually for the time being.
    raise NotImplementedError


def is_autoquit_in_box(box_dirpath):
    try:
        locate_autoquit_in_box(box_dirpath)
        return True
    except AutoQuitNotFoundError:
        return False


class AutoQuitNotFoundError(Exception):
    pass

def locate_autoquit_in_box(box_dirpath):
    boot_disk_image_filepath = locate_boot_volume_of_box(box_dirpath)
    
    # TODO: Eventually need to also check for the AutoQuit variant of this
    #       program for System 6 and below.
    autoquit_dirpath_components = ['System Folder', 'AutQuit7']
    
    if hfs2_exists(boot_disk_image_filepath, autoquit_dirpath_components):
        return (boot_disk_image_filepath, autoquit_dirpath_components)
    else:
        raise AutoQuitNotFoundError


class BootVolumeNotFoundError(Exception):
    pass

def locate_boot_volume_of_box(box_dirpath):
    for disk_image_filepath in volumes_of_box(box_dirpath):
        if hfs2_exists(disk_image_filepath, ['System Folder']):
            return disk_image_filepath
    raise BootVolumeNotFoundError


def volumes_of_box(box_dirpath):
    mount_dirpath = os.path.join(box_dirpath, 'mount')
    
    for root, dirs, files in os.walk(mount_dirpath):
        for file in files:
            # FIXME: Determine emulator type of box first to determine what
            #        types of disk images are supported. Here we assume that
            #        the box is a Basilisk box.
            if is_basilisk_supported_disk_image(file):
                yield os.path.join(root, file)

#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# set_autoquit_app

def set_autoquit_app(box_dirpath, disk_image_filepath, app_filepath_components):
    (boot_disk_image_filepath, autoquit_dirpath_components) = locate_autoquit_in_box(box_dirpath)
    
    autoquit_app_alias_filepath_components = autoquit_dirpath_components + ['app']
    if hfs2_exists(boot_disk_image_filepath, autoquit_app_alias_filepath_components):
        hfs2_delete(boot_disk_image_filepath, autoquit_app_alias_filepath_components)
    
    create_alias_file_2(
        boot_disk_image_filepath, autoquit_app_alias_filepath_components,
        disk_image_filepath, app_filepath_components)


def run_box(box_dirpath):
    try:
        box_up.main([box_dirpath])
    except SystemExit as e:
        if e.code == 0:
            pass
        else:
            raise
    print

# ------------------------------------------------------------------------------
# TODO: Make consistent and extract to classicbox.alias.file

def create_alias_file_2(
        output_disk_image_filepath, output_filepath_components,
        target_disk_image_filepath, target_filepath_components):
    
    output_macitempath = _mount_disk_image_and_resolve_path(
        output_disk_image_filepath, output_filepath_components)
    target_macitempath = _mount_disk_image_and_resolve_path(
        target_disk_image_filepath, target_filepath_components)
    create_alias_file(
        output_disk_image_filepath, output_macitempath,
        target_disk_image_filepath, target_macitempath)

# ------------------------------------------------------------------------------
# TODO: Make consistent and extract to classicbox.disk.hfs

def hfs2_exists(disk_image_filepath, itempath_components):
    macitempath = _mount_disk_image_and_resolve_path(disk_image_filepath, itempath_components)
    return hfs_exists(macitempath)


def hfs2_delete(disk_image_filepath, itempath_components):
    macitempath = _mount_disk_image_and_resolve_path(disk_image_filepath, itempath_components)
    hfs_delete(macitempath)


def hfs2_delete_if_exists(disk_image_filepath, itempath_components):
    if hfs2_exists(disk_image_filepath, itempath_components):
        hfs2_delete(disk_image_filepath, itempath_components)


def hfs2_ls(disk_image_filepath, itempath_components):
    macitempath = _mount_disk_image_and_resolve_path(disk_image_filepath, itempath_components)
    return hfs_ls(macitempath)


def hfs2_stat(disk_image_filepath, itempath_components):
    macitempath = _mount_disk_image_and_resolve_path(disk_image_filepath, itempath_components)
    return hfs_stat(macitempath)


def _mount_disk_image_and_resolve_path(disk_image_filepath, itempath_components):
    volume_info = hfs_mount(disk_image_filepath)
    volume_name = volume_info['name']
    
    macitempath = '%s:%s' % (volume_name, ':'.join(itempath_components))
    return macitempath

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main(sys.argv[1:])