from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.exceptions import (
    TemplateSyntaxError,
    TemplateRuntimeError,
)
from .base import StateExtension

class StateMetadataExtension(StateExtension):
    context_key = 'metadata'
    tags = frozenset(['define', 'deploy', 'action'])
    config = {
        'file': {
            'user':   (False, lambda v: v),
            'group':  (False, lambda v: v),
            'mode':   (False, lambda v: int(v, 8)),
        },
        'symlink': {
            'user':   (False, lambda v: v),
            'group':  (False, lambda v: v),
            'mode':   (False, lambda v: int(v, 8)),
            'target': (True,  lambda v: v),
        },
    }

    def init_state(self, state):
        state.type = None

    def parse(self, parser):
        if node := super().parse(parser):
            return node

        token = next(parser.stream)
        return getattr(self, f'parse_{token.value}')(
            parser, token, token.lineno
        )

    def parse_define(self, parser, token, lineno):
        parser.stream.expect('name:action')
        return nodes.CallBlock(
            self.call_method('_define', [
                nodes.ContextReference(),
                nodes.Const(self._parse_dotted_name(parser))
            ], lineno=lineno),
            [], [], [], lineno=lineno
        )

    def parse_deploy(self, parser, token, lineno):
        args = [nodes.ContextReference()]
        tpe = 'file'

        if parser.stream.current.type != 'block_end':
            key = parser.stream.expect('name')
            second = next(parser.stream)

            if second.type != 'assign':
                tpe = key.value
                key = second
                parser.stream.expect('assign')

        if (config := self.config.get(tpe)) is None:
            raise TemplateSyntaxError(
                f"Invalid thincf type '{tpe}'.", lineno
            )

        reqs = [k for k,(req,_) in config.items() if req]

        def append_config(key, value):
            if key not in config:
                raise TemplateSyntaxError(
                    f"Invalid keyword '{key}' for thincf type '{tpe}'.",
                    lineno
                )

            args.append(nodes.Const(key))
            args.append(value)

            if key in reqs:
                reqs.remove(key)

        args.append(nodes.Const(tpe))

        if parser.stream.current.type != 'block_end':
            append_config(key.value, parser.parse_expression())

        while parser.stream.current.type != 'block_end':
            key = parser.stream.expect('name')
            parser.stream.expect('assign')
            append_config(key.value, parser.parse_expression())

        if reqs:
            reqs = ','.join(f"'{r}'" for r in reqs)
            raise TemplateSyntaxError(
                f"Missing required keyword(s) {reqs} for thincf type '{tpe}'.",
                lineno
            )

        return nodes.CallBlock(
            self.call_method('_deploy', args, lineno=lineno),
            [], [], [], lineno=lineno
        )

    def parse_action(self, parser, token, lineno):
        args = [
            nodes.ContextReference(),
            nodes.Const(self._parse_dotted_name(parser))
        ]

        if parser.stream.current.type == 'lparen':
            next(parser.stream)
            require_comma = False
            while parser.stream.current.type != 'rparen':
                if require_comma:
                    parser.stream.expect('comma')
                    if parser.stream.current.type == 'rparen':
                        break

                args.append(parser.parse_expression())
                require_comma = True

        parser.stream.expect('rparen')

        return nodes.CallBlock(
            self.call_method('_action', args, lineno=lineno),
            [], [], [], lineno=lineno
        )

    def _parse_dotted_name(self, parser):
        name = parser.stream.expect('name').value
        while parser.stream.current.type == 'dot':
            next(parser.stream)
            name += '.' + parser.stream.expect('name').value
        return name

    @StateExtension.with_state
    def _deploy(self, state, ctx, tpe, *args, caller):
        if state.type is not None:
            raise

        config = self.config[tpe]
        state.type = tpe
        state.config = {}

        for key,value in zip(*[iter(args)] * 2):
            _,conv = config[key]
            state.config[key] = conv(value)

        return ''

    @StateExtension.with_state
    def _define(self, state, ctx, name, caller):
        if state.type is not None:
            raise
        else:
            state.type = 'action'
            state.name = name
        return ''

    @StateExtension.with_state
    def _action(self, state, ctx, name, *arguments, caller):
        state.actions.add((name, arguments))
        return ''

class StateMarkupExtension(Extension):
    tags = frozenset(['paragraph'])

    def parse(self, parser):
        token = next(parser.stream)
        return getattr(self, f'parse_{token.value}')(
            parser, token, token.lineno
        )

    def parse_paragraph(self, parser, token, lineno):
        return nodes.Output([nodes.Const('\n')], lineno=lineno)
