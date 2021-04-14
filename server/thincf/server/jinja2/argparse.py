from click import Group,Command,Argument,Option,get_current_context
from click.exceptions import UsageError

class ArgumentParserHelp(RuntimeError):
    def __init__(self, ctx):
        self.msg = ctx.get_help()

class ArgumentParserMode:
    def __init__(self, cmd):
        self.cmd = cmd

    def epilog(self, caller):
        self.cmd.epilog = caller()
        return ''

    def add_argument(self, name, required=None, default=None, nargs=1):
        self.cmd.params.append(Argument(
            param_decls=[name],
            required=required,
            default=default,
            nargs=nargs,
        ))
        return ''

    def add_option(self, *params_decl, required=False, is_flag=None):
        self.cmd.params.append(Option(
            param_decls=params_decl,
            required=required,
            is_flag=is_flag,
        ))
        return ''

class ArgumentParserContext:
    def raise_help(ctx, opt, val):
        if val:
            raise ArgumentParserHelp(ctx)

    help_option = Option(
        param_decls=['-h', '--help'],
        default=False,
        is_flag=True,
        is_eager=True,
        callback=raise_help,
    )

    def __init__(self, prog, args):
        self.prog = prog
        self.args = args
        self.root = Group(
            invoke_without_command=True,
            callback=self.callback(),
        )
        self.root.params.append(self.help_option)

    def add_mode(self, name, help=None):
        cmd = Command(name, callback=self.callback(name), help=help)
        cmd.params.append(self.help_option)
        self.root.add_command(cmd)
        return ArgumentParserMode(cmd)

    def callback(self, mode=None):
        def cb(**kwargs):
            ctx = get_current_context()
            ctx.obj.update(kwargs)
            ctx.obj['mode'] = mode
            return ctx.obj
        return cb

    def parse(self):
        try:
            obj = {}
            ctx = self.root.make_context(
                self.prog, self.args,
                help_option_names=[],
                obj=obj,
            )
            args = self.root.invoke(ctx)
            if args.get('mode') is None:
                raise ArgumentParserHelp(ctx)
            return args

        except ArgumentParserHelp as exc:
            return dict(
                mode='help',
                usage=exc.msg,
            )

        except UsageError as exc:
            return dict(
                mode='error',
                message=str(exc),
                usage=exc.ctx.get_help(),
            )
