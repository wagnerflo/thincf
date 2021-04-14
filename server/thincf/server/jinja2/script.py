from jinja2 import nodes
from jinja2.ext import Extension

class ScriptDoExtension(Extension):
    tags = frozenset(['do'])

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        expr = parser.parse_expression()
        return nodes.CallBlock(
            self.call_method('_do', [expr], lineno=lineno),
            [], [], [], lineno=lineno
        )

    def _do(self, expr, caller):
        return expr if expr else ''
