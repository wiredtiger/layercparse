#!/usr/bin/env python3

""" Access checker script.

This script checks that WiredTiger sources comply with modularity rules
described in MODULARITY.md.

"""

import sys, os
import glob

# layercparse is a library written and maintained by the WiredTiger team.
import layercparse as lcp

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
    # lcp.setLogLevel(lcp.LogLevel.WARNING)
    lcp.Log.module_name_mismatch.enabled = False
    print(f"Loading wt_defs.py from: {wt_defs_path}")

    rootPath = os.path.realpath(sys.argv[1])
    lcp.setRootPath(rootPath)
    lcp.setModules(wt_defs.modules)

    files = lcp.get_files()  # list of all source files
    for file in wt_defs.extraFiles:
        files.insert(0, os.path.join(os.path.realpath(rootPath), file))

    _globals = lcp.Codebase()
    # print(" ===== Scan")
    for macro in wt_defs.extraMacros:
        _globals.addMacro(**macro)
    _globals.scanFiles(files)
    # _globals.scanFiles(files, twopass=True, multithread=False)
    # print(" ===== Globals:")
    # pprint(_globals, width=120, compact=False)
    # print(" =====")

    # print(" ===== Access check:")
    # print(" ===== Check")
    lcp.AccessCheck(_globals).checkAccess()
    # AccessCheck(_globals).checkAccess(multithread=False)

    # import cProfile as p
    # pr = p.Profile()
    # pr.runctx('AccessCheck(_globals).checkAccess(multithread=False)', globals=globals(), locals=locals())
    # pr.create_stats()
    # pr.dump_stats("q")

    return not lcp.workspace.errors

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, BrokenPipeError):
        print("\nInterrupted")
        sys.exit(1)
    except OSError as e:
        print(f"\n{e.strerror}: {e.filename}")
        sys.exit(1)

