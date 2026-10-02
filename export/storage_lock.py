"""Coordinate CSV writers across scraper processes and browser imports."""
import os
from contextlib import contextmanager
from functools import wraps
import config


@contextmanager
def data_write_lock():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (config.DATA_DIR / ".data_write.lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def locked_storage(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with data_write_lock():
            return function(*args, **kwargs)
    return wrapped
