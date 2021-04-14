from asyncio import get_running_loop
from datetime import datetime,timezone
from errno import ENOTEMPTY
from functools import partial
from jinja2 import Environment,ChoiceLoader,FileSystemLoader,PackageLoader
from logging import getLogger
from pathlib import Path
from shutil import rmtree
from starlette.applications import Starlette
from starlette.datastructures import ImmutableMultiDict
from starlette.middleware import Middleware
from starlette.responses import Response
from starlette.routing import Route
from tempfile import mkdtemp
from urllib.parse import unquote
from x509middleware.asgi import ClientCertificateMiddleware

from .config import *
from .exceptions import (
    BadRequest,
    InternalServerError,
    ServiceUnavailable,
)
from .jinja2 import *
from .state import State
from .util import (
    requires_client_name,
    resolve_relative,
    tariter,
)

log = getLogger(__name__)

class ThincfServer(Starlette):
    async def execute(self, func, *args, **kws):
        return await get_running_loop().run_in_executor(
            None, partial(func, *args, **kws)
        )

    @requires_client_name
    async def upload_state(self, request, client_name):
        tmp = Path(await self.execute(mkdtemp, dir=STATEDIR))

        async def iterate_stream():
            async for tarinfo,data in tariter(request.stream()):
                if tarinfo.isdir():
                    continue

                if not tarinfo.isfile():
                    raise BadRequest(
                        f"File '{tarinfo.name}' is no file."
                    )

                if (name := resolve_relative(tarinfo.name)) is None:
                    raise BadRequest(
                        f"File '{tarinfo.name}' points outside of root."
                    )

                yield name,data.decode('utf8')
                filename = tmp / name
                await self.execute(filename.parent.mkdir, parents=True, exist_ok=True)
                await self.execute(filename.write_bytes, data)

        try:
            state = await State.from_iterator(
                datetime.now(timezone.utc).astimezone().isoformat(
                    timespec='microseconds'
                ),
                iterate_stream(),
            )

            await self.execute(tmp.rename, STATEDIR / state.identifier)

        except Exception as exc:
            await self.execute(rmtree, tmp)
            log.warn('Error importing state', exc_info=True)
            raise BadRequest(f"Submitted state is invalid: {exc}")

        self.state.state = state
        return Response(status_code=201)

    @requires_client_name
    async def get_script(self, request, client_name):
        # commandline arguments passed to client
        if not (args := request.headers.getlist('thincf-args')):
            raise BadRequest(f'Client commandline arguments missing.')

        # parse environment headers
        env = ImmutableMultiDict(
            (key, unquote(part.strip(), errors='surrogateescape'))
            for (b,s,key),val in (
                (key.partition('thincf-env-'),val)
                for key,val in request.headers.items()
            ) if not b
            for part in val.split(',')
        )

        # list of states client knows about
        states = [
            part.strip()
            for hdr in request.headers.getlist('thincf-states')
            for part in hdr.split(',')
        ]

        # get a reference to the current state so we're not left hanging
        # if it gets replaced while generating this response
        if (state := self.state.state) is None:
            raise ServiceUnavailable(f"No state installed.")

        # look up host by client name
        if (host := state.find_host(client_name=client_name)) is None:
            raise ServiceUnavailable(f"Client '{client_name}' unknown.")

        # set up arguments and parser
        args = [
            unquote(arg.strip(), errors='surrogateescape')
            for part in args for arg in part.split(',')
        ]
        argparser = ArgumentParserContext(args.pop(0), args)

        try:
            tmpl = self.state.jinja.get_template('main')
            body = tmpl.render(
                state = state.evaluate(host, states, env),
                argparser = argparser,
                env = env,
            )
            return Response(
                body,
                media_type='text/plain',
                headers={ 'thincf-shell': 'sh' },
            )

        except Exception as exc:
            log.warn('Error rendering template', exc_info=True)
            raise InternalServerError(
                f"Error generating script.\n  {exc.__class__.__name__}: {exc}"
            )

    async def on_startup(self):
        loaders = [PackageLoader(__name__, 'templates')]

        if TEMPLATEDIR is not None:
            loaders.insert(0, FileSystemLoader(TEMPLATEDIR))

        self.state.jinja = Environment(
            loader = ChoiceLoader(loaders),
            extensions = (
                ShellFunctionExtension,
                ScriptDoExtension,
                ShellEscapeExtension,
            ),
            line_statement_prefix = '%',
            line_comment_prefix = '##',
            keep_trailing_newline = True,
        )

        self.state.state = None

        async def iterate_directory(path):
            for item in path.glob('**/*'):
                if item.is_file():
                    yield item.relative_to(path),item.read_text('utf8')

        for candidate in sorted(STATEDIR.iterdir(), reverse=True):
            try:
                self.state.state = await State.from_iterator(
                    candidate.name,
                    iterate_directory(candidate),
                )
            except:
                log.warn(f"Unable to load state {candidate.name}",
                         exc_info=True)
            else:
                break

    def __init__(self, debug=False):
        middleware = []

        if CLIENT_NAME_HEADER is None:
            middleware.append(
                Middleware(
                    ClientCertificateMiddleware,
                    proxy_header=CLIENT_CERT_HEADER,
                ),

            )

        super().__init__(
            debug=debug,
            routes=[
                Route('/', self.get_script, methods=['GET']),
                Route('/', self.upload_state, methods=['POST']),
            ],
            middleware=middleware,
            on_startup=[
                self.on_startup,
            ],
        )

app = ThincfServer(debug=True)
