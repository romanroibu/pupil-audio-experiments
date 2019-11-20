# TODO: Remove once pupil_audio is installable with pip

import sys
import pathlib

# Re-export pupil_audio API
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.absolute()))
from pupil_audio import *
del sys.path[0]
