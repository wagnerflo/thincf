from asyncio import (
    Queue as AsyncQueue,
    create_task,
    get_running_loop,
    wait as async_wait,
    FIRST_COMPLETED,
)
from configparser import (
    ConfigParser,
    Interpolation,
    InterpolationMissingOptionError,
)
from functools import wraps
from io import RawIOBase
from pathlib import Path
from queue import Queue
from re import compile as regex
from starlette.datastructures import ImmutableMultiDict
from tarfile import TarFile

from . import config
from .exceptions import BadRequest,Forbidden

def resolve_relative(*path):
    try:
        return Path('/root', *path).resolve().relative_to('/root')
    except ValueError:
        pass

def requires_client_name(method):
    @wraps(method)
    async def _impl(self, request, *args, **kwargs):
        client_name = None
        if client_cert := request.scope.get('client_cert'):
            client_name = client_cert.subject.native['common_name']
        elif hdr := config.CLIENT_NAME_HEADER:
            client_name = request.headers.get(hdr)
        if not client_name:
            raise Forbidden(f"Cannot identify client.")
        return await method(self, request, *args, client_name, **kwargs)
    return _impl

def isplit(sliceable, index):
    return sliceable[:index],sliceable[index:]

def memcpy(dest, src):
    l = len(src)
    dest[:l] = src
    return l

class ChunkReader(RawIOBase):
    def __init__(self, get_next_chunk):
        self.get_next_chunk = get_next_chunk
        self.cur = None

    def readable(self):
        return True

    def readinto(self, buf):
        # if we don't have data left ask for a chunk
        if not self.cur:
            if not (cur := self.get_next_chunk()):
                return 0

            self.cur = memoryview(cur)

        # slice off size of buf from front of cur
        front,self.cur = isplit(self.cur, len(buf))

        # copy front into buf
        return memcpy(buf, front)

async def tariter(bytestream, executor=None, compression='*'):
    loop = get_running_loop()
    bq = Queue()
    rq = AsyncQueue()

    def extract():
        loop.call_soon_threadsafe(rq.put_nowait, True)
        tar = TarFile.open(
            fileobj=ChunkReader(bq.get),
            mode=f'r|{compression}'
        )
        while tarinfo := tar.next():
            if tarinfo.isfile():
                data = tar.extractfile(tarinfo).read()
            else:
                data = None
            loop.call_soon_threadsafe(rq.put_nowait, (tarinfo, data))

    # schedule extract to be run in thread and wait for start signal
    extract = loop.run_in_executor(executor, extract)
    if not await rq.get():
        return

    # send chunks of data to the thread
    async for chunk in bytestream:
        bq.put(chunk)

        # end of data
        if not chunk:
            # build awaitable set consisting of extract thread
            aws = set([extract])

            # as long as we have something to wait for...
            while aws:
                # if that something is just the thread future, add task
                # to also wait for result
                if not aws.difference([extract]):
                    aws.add(create_task(rq.get()))

                # wait for at least one future to complete and resolve
                done,aws = await async_wait(
                    aws, return_when=FIRST_COMPLETED
                )
                for fut in done:
                    # either the thread is complete
                    if fut is extract:
                        fut.result()
                    # or it's just a result from the queue
                    else:
                        yield fut.result()

        # drain result queue without waiting
        while not rq.empty():
            yield rq.get_nowait()

        # (premature) end of thread?
        if extract.done():
            break

def update_hash(h, *entries):
    for entry in entries:
        if not isinstance(entry, bytes):
            entry = str(entry).encode('utf-8')
        h.update(entry)
        h.update(len(entry).to_bytes(4, 'big'))

class item:
    def __init__(self):
        self.values = []

    def push(self, *values):
        self.values.extend(values)

    def append(self, value):
        self.values[-1] += f"\n{value}"

    def clear(self):
        self.values.clear()

    def __repr__(self):
        return repr(self.values)

    def __len__(self):
        return len(self.values)

    def __getitem__(self, key):
        return self.values[key]

class multi_dict(dict):
    def __setitem__(self, key, value):
        if isinstance(value, list):
            if key not in self:
                super().__setitem__(key, item())
            self[key].push(*value)
        else:
            super().__setitem__(key, value)

class MultiInterpolator(Interpolation):
    ARRAY_IPOL_RE = regex(r'^@\{([^}]+)\}$')
    STRING_IPOL_RE = regex(r'\$\{([^}]+)\}')

    def __init__(self, ipol_src_section):
        self.ipol_src = ipol_src_section

    def before_get(self, parser, section, option, value, defaults):
        if section == self.ipol_src:
            return value

        res = item()

        def get_replacement(val, key):
            try:
                return parser.get(self.ipol_src, key)
            except:
                raise InterpolationMissingOptionError(
                    option, section, val, key
                )

        for val in value:
            if val == '!{clear}':
                res.clear()
            elif (match := self.ARRAY_IPOL_RE.match(val)) is not None:
                res.push(*get_replacement(val, match.group(1)))
            else:
                res.push(self._interpolate_string(get_replacement, val))

        return res

    def _interpolate_string(self, get_replacement, val):
        res = ''
        idx = 0

        for match in self.STRING_IPOL_RE.finditer(val):
            repl = get_replacement(val, match.group(1))
            if len(repl) != 1:
                raise
            res += f'{val[idx:match.start()]}{repl[0]}'
            idx = match.end()

        return f'{res}{val[idx:]}'

INI_SECTCRE = regex(r'\[ *(?P<header>[^]]+?) *\]')
INTERPOLATOR = MultiInterpolator('META')

def read_ini(name, data):
    parser = ConfigParser(
        comment_prefixes = ('#',),
        inline_comment_prefixes = ('#',),
        default_section = None,
        interpolation = INTERPOLATOR,
        strict = False,
        allow_no_value = True,
        dict_type = multi_dict,
    )
    parser.SECTCRE = INI_SECTCRE
    parser.read_string(data, name)
    return {
        section.strip(): ImmutableMultiDict(
            (key, val)
            for key,vals in parser.items(section)
            for val in ( [True] if vals is None else vals )
        )
        for section in parser.sections()
        if section != INTERPOLATOR.ipol_src
    }
