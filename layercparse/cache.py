import os, hashlib
from typing import Callable, Protocol

import pickle
# import marshal as pickle
# import json as pickle
# import sPickle as pickle
if getattr(pickle, "UnpicklingError", None) is None:
    pickle.UnpicklingError = ValueError

from .internal import *
from . import workspace


def getcachedir(dirname: str = ".parsecache") -> str:
    return os.path.join(workspace.rootPath, "build", dirname)

def mkcachedir(dirname: str = ".parsecache") -> str:
    path = getcachedir(dirname)
    os.makedirs(path, exist_ok=True)
    return path

class Packer:
    @staticmethod
    def load(file) -> object: ...
    @staticmethod
    def store(obj: object, file) -> None: ...

class PackPickle(Packer):
    @staticmethod
    def load(file) -> object:
        with open(file, "rb") as f:
            return pickle.load(f)
    @staticmethod
    def store(obj: object, file) -> None:
        with open(file, "wb") as f:
            pickle.dump(obj, f)

class PackString(Packer):
    @staticmethod
    def load(file) -> object:
        with open(file, "r") as f:
            return f.read()
    @staticmethod
    def store(obj: object, file) -> None:
        with open(file, "w") as f:
            f.write(obj)

# Caches pickled python objects to disk
# If the source file is newer than the cache file, the cache is considered invalid
class CacheFile:
    # Returns true if the object is in the cache
    @staticmethod
    def is_cached(srcpath: str,
                  suffix: str = "",
                  dirname: str = ".parsecache") -> bool:
        cachepath = os.path.join(getcachedir(dirname), os.path.relpath(srcpath, workspace.rootPath) + suffix)
        try:
            srcstat = os.stat(srcpath)
            cachestat = os.stat(cachepath)
            return (srcstat.st_mtime - cachestat.st_mtime) <= 1
        except FileNotFoundError:
            return False

    # Returns the object from the cache if it exists and is up to date
    @staticmethod
    def get(srcpath: str,
            suffix: str = "",
            packer = PackPickle,
            dirname: str = ".parsecache") -> object | None:
        cachepath = os.path.join(getcachedir(dirname), os.path.relpath(srcpath, workspace.rootPath) + suffix)
        # Use os.stat to compare file modification times and size
        try:
            srcstat = os.stat(srcpath)
            cachestat = os.stat(cachepath)
            if (srcstat.st_mtime - cachestat.st_mtime) > 1:
                return None
            return packer.load(cachepath)
        except (FileNotFoundError, pickle.UnpicklingError):
            return None

    # Pickles the object to the cache
    @staticmethod
    def put(obj: object,
            srcpath: str,
            suffix: str = "",
            packer = PackPickle,
            dirname: str = ".parsecache"):
        cachepath = os.path.join(mkcachedir(dirname), os.path.relpath(srcpath, workspace.rootPath) + suffix)
        os.makedirs(os.path.dirname(cachepath), exist_ok=True)
        packer.store(obj, cachepath)
        return obj

# Caches pickled python objects to disk
# The key is compuded from the content of the object
class CacheContent:
    # Returns the object from the cache if it exists and is up to date
    # The key is a big string. The actual key is computed by hashing it.
    @staticmethod
    def get(key: str,
            suffix: str = "",
            packer = PackPickle,
            dirname: str = ".parsecache") -> object | None:
        key = hashlib.sha1(key.encode()).hexdigest()
        cachepath = os.path.join(getcachedir(dirname), key + suffix)
        try:
            return packer.load(cachepath)
        except (FileNotFoundError, pickle.UnpicklingError):
            return None

    # Pickles the object to the cache
    # The key is a big string. The actual key is computed by hashing it.
    @staticmethod
    def put(obj: object,
            key: str,
            suffix: str = "",
            packer = PackPickle,
            dirname: str = ".parsecache"):
        key = hashlib.sha1(key.encode()).hexdigest()
        cachepath = os.path.join(mkcachedir(dirname), key + suffix)
        os.makedirs(os.path.dirname(cachepath), exist_ok=True)
        packer.store(obj, cachepath)

# Decorator that wraps a function or instance method with caching
def cached(cache = CacheFile,
           fileFn: Callable[..., str] | None = None,
           suffixFn: Callable[..., str] | None = None,
           packer = PackPickle):
    if not fileFn:
        raise ValueError("fileFn is required")
    if not suffixFn:
        suffixFn = lambda *args, **kwargs: ""
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = fileFn(*args, **kwargs)
            suffix = suffixFn(*args, **kwargs)
            if (obj := cache.get(key, suffix=suffix, packer=packer)) is not None:
                return obj
            obj = func(*args, **kwargs)
            cache.put(obj, key, suffix=suffix, packer=packer)
            return obj
        return wrapper
    return decorator

