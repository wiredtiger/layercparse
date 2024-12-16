#!/usr/bin/env python3

""" Source scan script.

This script scans WiredTiger.

"""

import sys, os
import glob

# layercparse is a library written and maintained by the WiredTiger team.
import layercparse as lcp
from layercparse.scan_sources_tool import scan_sources_main

home_dir = os.path.expanduser("~")
pattern = os.path.join(home_dir, '**', 'dist', 'access_check')
wt_defs_path = next(glob.iglob(pattern, recursive=True), None)

if wt_defs_path:
    sys.path.insert(0, os.path.abspath(wt_defs_path))
    import wt_defs
else:
    print("Error: 'wt_defs.py' not found.")
    sys.exit(1)

def main():
    lcp.Log.module_name_mismatch.enabled = False
    print(f"Loading wt_defs.py from: {wt_defs_path}")

    return scan_sources_main(extraFiles=wt_defs.extraFiles,
                             modules=wt_defs.modules,
                             extraMacros=wt_defs.extraMacros)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, BrokenPipeError):
        print("\nInterrupted")
        sys.exit(1)
    except OSError as e:
        print(f"\n{e.strerror}: {e.filename}")
        sys.exit(1)

