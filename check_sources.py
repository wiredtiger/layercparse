#!/usr/bin/env python3

import sys, os
from layercparse import *
from pprint import pprint, pformat

def main():
    # setLogLevel(LogLevel.WARNING)

    rootPath = os.path.realpath(sys.argv[1])
    setRootPath(rootPath)
    if workspace.errors:
        return False
    files = get_files()
    files.insert(0, os.path.join(os.path.realpath(rootPath), "src/include/wiredtiger.in"))

    _globals = Codebase()
    # print(" ===== Scan")
    _globals.scanFiles(files, twopass=True, multithread=True)
    # _globals.scanFiles(files, twopass=True, multithread=False)
    # print(" ===== Globals:")
    # pprint(_globals, width=120, compact=False)
    # print(" =====")

    # print(" ===== Access check:")
    # print(" ===== Check")
    AccessCheck(_globals).checkAccess(multithread=True)
    # AccessCheck(_globals).checkAccess(multithread=False)

    # import cProfile as p
    # pr = p.Profile()
    # pr.runctx('AccessCheck(_globals).checkAccess(multithread=False)', globals=globals(), locals=locals())
    # pr.create_stats()
    # pr.dump_stats("q")

    return not workspace.errors

if __name__ == "__main__":
    sys.exit(main())

