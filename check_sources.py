#!/usr/bin/env python3

""" Access checker script.

This script checks that WiredTiger sources comply with modularity rules
described in MODULARITY.md.

"""

import sys, os

# layercparse is a library written and maintained by the WiredTiger team.
import layercparse as lcp

def load_wt_defs(rootPath):
    wt_defs_path = os.path.join(rootPath, 'dist', 'access_check', 'wt_defs.py')
    with open(wt_defs_path, "r") as f:
        code = f.read()
    wt_defs = {}
    exec(code, {}, wt_defs)
    return wt_defs

def main():
    # lcp.setLogLevel(lcp.LogLevel.WARNING)
    lcp.Log.module_name_mismatch.enabled = False

    rootPath = os.path.realpath(sys.argv[1])
    lcp.setRootPath(rootPath)
    wt_defs = load_wt_defs(rootPath)
    lcp.setModules(wt_defs["modules"])

    files = lcp.get_files()  # list of all source files
    for file in wt_defs["extraFiles"]:
        files.insert(0, os.path.join(os.path.realpath(rootPath), file))

    _globals = lcp.Codebase()
    # print(" ===== Scan")
    for macro in wt_defs["extraMacros"]:
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

