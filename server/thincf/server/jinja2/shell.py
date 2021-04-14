from itertools import count,product
from jinja2 import nodes
from jinja2.ext import Extension
from shlex import quote as shquote

from .base import StateExtension

class ShellFunctionExtension(StateExtension):
    tags = frozenset(['declare', 'require'])

    def parse(self, parser):
        if node := super().parse(parser):
            return node

        token = next(parser.stream)
        lineno = token.lineno

        if token.value == 'declare':
            name = parser.parse_assign_target(name_only=True).name
            body = parser.parse_statements(('name:enddeclare',), drop_needle=True)
            return nodes.CallBlock(
                self.call_method('_declare', [
                    nodes.ContextReference(),
                    nodes.Const(name),
                ], lineno=lineno),
                [], [], body, lineno=lineno
            )

        elif token.value == 'require':
            key = parser.parse_assign_target(name_only=True)
            return nodes.CallBlock(
                self.call_method('_require', [
                    nodes.ContextReference(),
                    nodes.Const(key.name),
                ], lineno=lineno),
                [], [], [], lineno=lineno
            )

    def init_state(self, state):
        state.registry = {}
        state.imported = {}

    @StateExtension.with_state
    def _declare(self, state, ctx, name, caller):
        state.registry[name] = caller()
        return ''

    @StateExtension.with_state
    def _require(self, state, ctx, name, caller):
        if name not in state.imported:
            state.imported[name] = True
            return state.registry[name]
        return ''

class ShellEscapeExtension(Extension):
    heredoc_chars = (
        '^!%*+,.:<>?~@0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
        'abcdefghijklmnopqrstuvwxyz$"#&()-/=;[]_|${}'
    )
    tags = frozenset(['heredoc'])

    def __init__(self, environment):
        super().__init__(environment)
        environment.filters['shquote'] = self._shquote
        environment.filters['octescape'] = self._octescape

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        body = parser.parse_statements(['name:endheredoc'], drop_needle=True)
        return nodes.CallBlock(
            self.call_method('_heredoc', [], lineno=lineno),
            [], [], body, lineno=lineno
        )

    def _heredoc(self, caller):
        string = caller()
        if not string.endswith('\n'):
            string = string + '\n'
        for i in count(1):
            for word in product(self.heredoc_chars, repeat=i):
                word = ''.join(word)
                if word not in string:
                    return f"'{word}'\n{string}{word}\n"

    def _shquote(self, s):
        return shquote(str(s))

    def _octescape(self, s):
        return ''.join([
            '\\{:03o}'.format(c) for c in str(s).encode('utf8')
        ])
