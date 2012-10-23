#!/usr/bin/env python
"""
Given two catalog files, computes a diff of what changed.

Optionally, remove parts of the resultant diff that match an "ignoretree" file.

Catalog Format:
* See the documentation for the `catalog_create` program.

Catalog Diff Format:
* It's JSON. Strings are UTF-8 encoded.
* Grammar:
    * ROOT: DirectoryListingDiff
    * DirectoryListingDiff: (Deletes, Adds, Edits)
    * Deletes: <list of file/directory names that were deleted> : unicode[]
    * Adds: <list of file/directory names that were added> : unicode[]
    * Edits: <list of ItemDiff> : ItemDiff[]
    * ItemDiff: FileDiff | DirectoryDiff
    * FileDiff:      (name : unicode, (date1 : unicode, date2 : unicode))
    * DirectoryDiff: (name : unicode, (date1 : unicode, date2 : unicode), DirectoryListingDiff)

Ignore Tree Format:
* It's JSON. Strings are UTF-8 encoded.
* Grammar:
    * ROOT: IgnoredDirectoryListing
    * IgnoredDirectoryListing: [IgnoredItem, ...]
    * IgnoredItem: IgnoredFileOrDirectory | IgnoredDirectory
    * IgnoredFileOrDirectory: filename : unicode
    * IgnoredDirectory: [filename : unicode, IgnoredDirectoryListing]
"""

import json
import os.path
import pprint
import sys


def main(args):
    if len(args) > 0 and args[0] == '--pretty':
        pretty = True
        args = args[1:]
    else:
        pretty = False
    
    if len(args) not in [2, 3]:
        sys.exit('syntax: catalog_diff [--pretty] <file1.catalog.json> <file2.catalog.json> [<file3.ignoretree.json>]')
        return
    
    catalog1_filepath = args[0]
    catalog2_filepath = args[1]
    if not os.path.exists(catalog1_filepath):
        sys.exit('file not found: %s' % catalog1_filepath)
        return
    if not os.path.exists(catalog2_filepath):
        sys.exit('file not found: %s' % catalog2_filepath)
        return
    
    with open(catalog1_filepath, 'rb') as catalog1_file:
        catalog1 = json.loads(catalog1_file.read())
    with open(catalog2_filepath, 'rb') as catalog2_file:
        catalog2 = json.loads(catalog2_file.read())
    
    catalog_diff = diff_tree(catalog1, catalog2)
    
    # If an ignore tree is specified, remove elements from the diff
    # that the tree matches.
    if len(args) == 3:
        ignore_tree_filepath = args[2]
        with open(ignore_tree_filepath, 'rb') as ignore_tree_file:
            ignore_tree = json.loads(ignore_tree_file.read())
        
        remove_ignored_diff_parts(catalog_diff, ignore_tree)
    
    if pretty:
        pprint.pprint(catalog_diff)
    else:
        print json.dumps(catalog_diff, ensure_ascii=True)


EMPTY_DIFF = ([], [], [])

def diff_tree(tree1, tree2):
    # For files, determine (+) add, (-) delete, (%) edit
    # For directories, determine (+) add, (-) delete, (%) edit
    
    files1 = set()
    dirs1 = set()
    name_to_date1 = dict()
    name_to_descendants1 = dict()
    for item in tree1:
        if len(item) == 2:      # file
            (name, date_modified) = item
            
            files1.add(name)
            name_to_date1[name] = date_modified
        elif len(item) == 3:    # dir
            (name, date_modified, descendants) = item
            is_file = False
            
            dirs1.add(name)
            name_to_date1[name] = date_modified
            name_to_descendants1[name] = descendants
        else:
            raise ValueError
    
    files2 = set()
    dirs2 = set()
    name_to_date2 = dict()
    name_to_descendants2 = dict()
    for item in tree2:
        if len(item) == 2:      # file
            (name, date_modified) = item
            
            files2.add(name)
            name_to_date2[name] = date_modified
        elif len(item) == 3:    # dir
            (name, date_modified, descendants) = item
            is_file = False
            
            dirs2.add(name)
            name_to_date2[name] = date_modified
            name_to_descendants2[name] = descendants
        else:
            raise ValueError
    
    deletes = sorted(list(files1 - files2) + list(dirs1 - dirs2))    
    adds = sorted(list(files2 - files1) + list(dirs2 - dirs1))
    
    edits = []
    
    shared_files = files1 & files2
    for name in shared_files:
        date1 = name_to_date1[name]
        date2 = name_to_date2[name]
        
        if date1 != date2:
            edits.append((name, (date1, date2)))
    
    shared_dirs = dirs1 & dirs2
    for name in shared_dirs:
        date1 = name_to_date1[name]
        date2 = name_to_date2[name]
        descendants1 = name_to_descendants1[name]
        descendants2 = name_to_descendants2[name]
        
        descendants_diff = diff_tree(descendants1, descendants2)
        if date1 != date2 or descendants_diff != EMPTY_DIFF:
            edits.append((name, (date1, date2), descendants_diff))
    
    edits = sorted(edits)
    
    return (deletes, adds, edits)


def remove_ignored_diff_parts(diff, ignored_tree):
    """
    Removes the parts of `diff` that occur in `ignored_tree`,
    modifying it in place.
    """
    (deletes, adds, edits) = diff
    
    for i in xrange(len(deletes)-1, -1, -1):
        # Check whether this file/directory is marked to be ignored completely
        if deletes[i] in ignored_tree:
            del deletes[i]
    
    for i in xrange(len(adds)-1, -1, -1):
        # Check whether this file/directory is marked to be ignored completely
        if adds[i] in ignored_tree:
            del adds[i]
    
    i = 0
    while i < len(edits):
        cur_edit = edits[i]     # (name, (date1, date2), descendants_diff?)
        cur_edit_name = cur_edit[0]
        
        # Check whether this file/directory is marked to be ignored completely
        if cur_edit_name in ignored_tree:
            del edits[i]
            continue
        
        cur_edit_is_dir = len(cur_edit) == 3
        if cur_edit_is_dir:
            cur_edit_descendants = cur_edit[2]
            
            for ignored_dir in ignored_tree:
                if type(ignored_dir) == list:   # is directory?
                    (ignored_name, ignored_descendants) = ignored_dir
                    if cur_edit_name == ignored_name:
                        remove_ignored_diff_parts(cur_edit_descendants, ignored_descendants)
            
            # Everything inside this directory was ignored, so mark the
            # directory itself as ignored
            if cur_edit_descendants == EMPTY_DIFF:
                del edits[i]
                continue
        
        i += 1


if __name__ == '__main__':
    main(sys.argv[1:])