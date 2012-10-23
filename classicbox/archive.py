"""
Functions to examine and extract compressed archives.
"""

from classicbox.util import DEVNULL
import shutil
import subprocess
import tempfile


class ExtractedArchive(object):
    """
    Represents a compressed archive that has been extracted to a temporary directory.
    """
    
    def __init__(self, archive_filepath, extraction_dirpath):
        self.archive_filepath = archive_filepath
        self.extraction_dirpath = extraction_dirpath
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, traceback):
        self.close()
    
    def close(self):
        shutil.rmtree(self.extraction_dirpath)


# TODO: Alter default behavior to NOT extract resource forks natively,
#       as this behavior is not compatible with Windows.
def archive_extract(archive_filepath):
    """
    Extracts the specified archive to a temporary directory.
    
    Returns an ExtractedArchive object.
    
    This function is intended to be used in a `with` statement,
    so that the temporary extraction directory is eventually deleted.
    """
    
    extraction_dirpath = tempfile.mkdtemp()
    try:
        subprocess.check_call([
            'unar',
            # recursively extract inner archives by default
            '-forks', 'fork',   # save resource forks natively (OS X only)
            '-no-quarantine',   # don't display warnings upon launch of extracted apps
            '-no-directory',    # don't create an extra enclosing directory
            '-output-directory', extraction_dirpath,
            archive_filepath
        ], stdout=DEVNULL, stderr=DEVNULL)
        
        return ExtractedArchive(archive_filepath, extraction_dirpath)
    except:
        shutil.rmtree(extraction_dirpath)
        raise