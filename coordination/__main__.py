"""Allow `python -m coordination` as a shortcut for `python -m coordination.cli`."""

import sys

from coordination.cli import main

if __name__ == "__main__":
    sys.exit(main())
