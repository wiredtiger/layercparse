#!/usr/bin/env python3

""" Access checker script.

This script checks that WiredTiger sources comply with modularity rules
described in MODULARITY.md.

"""

import sys, os

# layercparse is a library written and maintained by the WiredTiger team.
import layercparse as lcp

CODE_CONFIG_REL_PATH = "dist/modularity/wt_defs.py"

def main():
    # lcp.setLogLevel(lcp.LogLevel.WARNING)
    lcp.Log.module_name_mismatch.enabled = False

    rootPath = os.path.realpath(sys.argv[1])
    lcp.setRootPath(rootPath)
    code_config = lcp.load_code_config(rootPath, CODE_CONFIG_REL_PATH)
    lcp.setModules(code_config["modules"])

    files = lcp.get_files()  # list of all source files
    for file in code_config["extraFiles"]:
        files.insert(0, os.path.join(os.path.realpath(rootPath), file))

    _globals = lcp.Codebase()
    # print(" ===== Scan")
    for macro in code_config["extraMacros"]:
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

