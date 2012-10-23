"""
Miscellaneous internal utilities.
"""

import os


"""
Constant that can be passed as the `stdout` or `stderr` arguments of
`subprocess.Popen` and similar functions.

Is not necessarily a file object.
"""
try:
    from subprocess import DEVNULL  # Python 3.3+
except:
    DEVNULL = open(os.devnull, 'wb')
