from collections import namedtuple
from jinja2 import Environment,FunctionLoader
from shlex import split as shsplit
from starlette.datastructures import ImmutableMultiDict
from re import compile as regex, escape as regex_escape

from .action import Invocation
from ..util import read_ini

class Directory:
    jinja_bool = Environment(
        loader = FunctionLoader(
            lambda name: (
                f'{{{{ ({name}) is true }}}}',
                name,
                lambda: True
            )
        ),
    )

    PATTERNS = (
        (r'/\*\*\*$', r'(?:/.+)?', (0, 100,   0,   0)),
        (r'\*\*',     r'.*',       (0,   0, 100,   0)),
        (r'\*',       r'[^/]*',    (0,   0,   0, 100)),
    )
    PATTERN = regex(
        '|'.join(fr'({pattern})' for pattern,_,_ in PATTERNS)
    )

    def __init__(self, pattern, config):
        pat = r'^'
        ord = (0, 0, 0, 0)
        idx = 0

        for match in self.PATTERN.finditer(pattern):
            _,repl,order = self.PATTERNS[match.lastindex-1]
            pat += fr'{regex_escape(pattern[idx:match.start()])}(?:{repl})'
            ord = tuple(i-j for i,j in zip(ord, order))
            idx = match.end()

        self.path = pattern
        self.pattern = regex(fr'{pat}{regex_escape(pattern[idx:])}$')
        self.order = ord
        self.config = config

    def __lt__(self, other):
        return self.order < other.order

    def matches_path(self, path):
        return bool(self.pattern.match(str(path)))

    @property
    def has_pattern(self):
        return self.order != (0, 0, 0, 0)

    def force_create(self, create_if, host, env):
        if self.has_pattern or create_if is None:
            return False

        template = self.jinja_bool.get_template(create_if.strip())
        return template.render(
            host = host,
            env = env,
        ) == 'True'

def split_action(var):
    cmd,*args = shsplit(var)
    return Invocation(cmd, tuple(args))

class Directories(list):
    Config = namedtuple(
        'Config',
        ('convert', 'get'),
        defaults=(
            lambda v: v,
            ImmutableMultiDict.get,
        )
    )

    config = {
        'user':      Config(),
        'group':     Config(),
        'mode':      Config(convert=lambda v: int(v, 8)),
        'action':    Config(convert=split_action,
                            get=ImmutableMultiDict.getlist),
        'create_if': Config(),
    }

    @classmethod
    def from_str(cls, name, data):
        return cls(
            sorted(
                Directory(
                    section,
                    ImmutableMultiDict(
                        (key, cls.config[key].convert(val))
                        for key,val in items.multi_items()
                    )
                )
                for section,items in read_ini(name, data).items()
            )
        )

    def evaluate(self, path):
        config = {}

        for item in self:
            if item.matches_path(path):
                config.update({
                    key: self.config[key].get(item.config, key)
                    for key in item.config.keys()
                })

        return config
