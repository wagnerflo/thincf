from os import environ
from starlette.config import Config,undefined
from starlette.datastructures import CommaSeparatedStrings
from pathlib import Path

def exists_and_dir(config, key, default=undefined):
    val = config(key, cast=Path, default=default)
    if not val:
        return val
    if not val.exists():
        raise KeyError(f"{key} = '{val}' doesn't exist.")
    if not val.is_dir():
        raise KeyError(f"{key} = '{val}' is no directory.")
    return val

config = Config(environ.get('THINCF_SERVER_DOTENV'))

STATEDIR = exists_and_dir(config, 'THINCF_SERVER_STATEDIR')
TEMPLATEDIR = exists_and_dir(config, 'THINCF_SERVER_TEMPLATEDIR', default=None)
CLIENT_NAME_HEADER = config('THINCF_SERVER_CLIENT_NAME_HEADER', default=None)
CLIENT_CERT_HEADER = config('THINCF_SERVER_CLIENT_CERT_HEADER', default=None)

__all__ = (
    'STATEDIR',
    'TEMPLATEDIR',
    'CLIENT_NAME_HEADER',
    'CLIENT_CERT_HEADER',
)
