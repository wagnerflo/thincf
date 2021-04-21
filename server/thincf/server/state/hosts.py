from collections import namedtuple
from re import compile as regex, escape as regex_escape
from ..util import read_ini

FindKey = namedtuple('FindKey', ('value', 'wildcard'))

class Host:
    PATTERNS = (
        (r'\*', r'.+'),
    )
    PATTERN = regex(
        '|'.join(fr'({pattern})' for pattern,_ in PATTERNS)
    )

    def __init__(self, name, config):
        self.name = name
        self.config = config

    def __contains__(self, pattern):
        try:
            next(self.find(pattern, only_values=True))
            return True
        except StopIteration:
            return False

    def __getitem__(self, pattern):
        try:
            return next(self.find(pattern, only_values=True))
        except StopIteration:
            raise KeyError(pattern)

    def find(self, pattern, only_values=False):
        pat = r'^'
        idx = 0
        for match in self.PATTERN.finditer(pattern):
            _,repl = self.PATTERNS[match.lastindex-1]
            pat += fr'{regex_escape(pattern[idx:match.start()])}({repl})'
            idx = match.end()
        pat = regex(fr'{pat}{regex_escape(pattern[idx:])}$')

        for key,value in self.config.multi_items():
            if (m := pat.match(key)) is None:
                continue

            if only_values:
                yield value
            else:
                try:
                    wildcard = m.group(1)
                except IndexError:
                    wildcard = None
                yield ( FindKey(m.group(0), wildcard), value )

class Hosts(dict):
    @classmethod
    def from_str(cls, name, data):
        return cls({
            section: Host(section, items)
            for section,items in read_ini(name, data).items()
        })
