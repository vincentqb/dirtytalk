import sys

# Workaround for name of cli to be same as name of module
sys.path.pop(0)

from dirtytalk import dirtytalk_from_args

__all__ = ["dirtytalk_from_args"]
