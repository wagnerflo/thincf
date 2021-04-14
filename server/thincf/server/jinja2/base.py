from asyncio import iscoroutinefunction
from functools import wraps
from jinja2 import nodes,lexer
from jinja2.ext import Extension,ExtensionRegistry
from types import SimpleNamespace

class InitExtensionMeta(ExtensionRegistry):
    def __new__(mcs, name, bases, d):
        if 'tags' in d:
            init_tag = f'_init_{name}'
            d.update(
                _init_tag = init_tag,
                tags = frozenset([init_tag] + list(d['tags'])),
            )
        return super().__new__(mcs, name, bases, d)

class InitExtension(Extension,metaclass=InitExtensionMeta):
    def filter_stream(self, stream):
        yield lexer.Token(0, 'block_begin', '%')
        yield lexer.Token(0, 'name', self._init_tag)
        yield lexer.Token(0, 'block_end', '')
        for token in stream:
            yield token

    def parse(self, parser):
        if not parser.stream.current.test(f'name:{self._init_tag}'):
            return

        lineno = next(parser.stream).lineno
        return nodes.CallBlock(
            self.call_method('_init', [
                nodes.ContextReference()
            ],
                lineno=lineno,
            ),
            [], [], [], lineno=lineno
        )

class StateExtension(InitExtension):
    @property
    def context_key(self):
        return f'_{self.__class__.__qualname__}_state'

    def _init(self, ctx, caller):
        if self.context_key not in ctx.parent:
            state = SimpleNamespace()
            self.init_state(state)
            ctx.parent[self.context_key] = state
        return ''

    def init_state(self, state):
        pass

    def with_state(func):
        @wraps(func)
        def wrapper(self, ctx, *args, **kws):
            return func(self, ctx[self.context_key], ctx, *args, **kws)
        return wrapper
