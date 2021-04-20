from hashlib import blake2b
from jinja2 import Environment,FunctionLoader
from pathlib import Path
from re import compile as regex
from types import SimpleNamespace

from ..util import update_hash
from ..jinja2 import *
from .action import *
from .dirs import Directories
from .files import *
from .hosts import Hosts

class State:
    person_client = b'thincf.cl.state'

    def __init__(self, identifier, hosts, dirs, files, actions):
        self.identifier = identifier
        self.hosts = hosts
        self.dirs = dirs
        self.files = files
        self.actions = actions
        self.jinja_files = Environment(
            loader = FunctionLoader(self.load_template),
            extensions = (
                StateMetadataExtension,
                StateMarkupExtension,
            ),
            line_statement_prefix = '%%',
        )

    @classmethod
    async def from_iterator(cls, identifier, iterator):
        hosts = None
        dirs = None
        files = {}
        actions = {}

        async for filename,content in iterator:
            if str(filename) == 'hosts.ini':
                hosts = Hosts.from_str(filename.name, content)

            elif str(filename) == 'dirs.ini':
                dirs = Directories.from_str(filename.name, content)

            else:
                files[filename] = content

        if hosts is None:
            raise Exception("hosts.ini missing")

        if dirs is None:
            dirs = Directories()

        return cls(identifier, hosts, dirs, files, actions)

    def find_host(self, client_name):
        return self.hosts.get(client_name)

    def load_template(self, name):
        if (content := self.files.get(Path(name))) is not None:
            return (content, name, lambda: True)

    def evaluate_file(self, path, host, env):
        template = self.jinja_files.get_template(str(path))
        metadata = SimpleNamespace(
            type = None,
            actions = set(),
        )
        content = template.render(
            hosts = list(self.hosts.values()),
            host = host,
            env = env,
            metadata = metadata,
        )

        if metadata.type is None:
            return

        elif metadata.type == 'action':
            return Action(metadata.name, content)

        elif metadata.type == 'symlink':
            return SymlinkEntry(
                path, **metadata.config,
                actions=[Invocation(*act) for act in metadata.actions],
            )

        elif metadata.type == 'file':
            return FileEntry(
                path, content, **metadata.config,
                actions=[Invocation(*act) for act in metadata.actions],
            )

        raise

    def evaluate_dir(self, path):
        return DirEntry(path, **self.dirs.evaluate(path))

    def evaluate(self, host, states, env):
        entries = {}
        actions = {}

        # walk all files and evaluate them
        for path,item in self.files.items():
            entry = self.evaluate_file(path, host, env)

            if entry is None:
                continue

            elif isinstance(entry, Action):
                actions[entry.name] = entry

            else:
                entries[path] = entry

        # also add all none-pattern entries from the directory list,
        # that are explicitly requested for this host
        for d in self.dirs:
            if (path := Path(d.path)) not in entries:
                entry = self.evaluate_dir(path)
                if d.force_create(entry.create_if, host, env):
                    entries[path] = entry

        # add all parents
        for path in list(entries.keys()):
            for part in path.parents:
                if part not in entries:
                    entries[part] = self.evaluate_dir(part)

        # turn it into a sorted list
        entries = [
            entries[item] for item in sorted(entries.keys())
        ]

        # strip actions not required by any entries and create indices
        # across action names and arguments
        def mkidx(iterable):
            return (
                (b,a) for a,b in
                enumerate(sorted(set(iterable)), start=1)
            )

        invocations = set(i for entry in entries for i in entry.actions)
        actions = {
            name: SimpleNamespace(
                action = actions[name],
                index = action_index,
                args = dict(mkidx(
                    i.arguments for i in invocations if i.name == name
                )),
            )
            for name,action_index in mkidx(i.name for i in invocations)
        }

        # create identifier hash
        h = blake2b(digest_size=20, person=self.person_client)
        update_hash(h, self.identifier)

        for entry in entries:
            entry.add_to_hash(h)

        for entry in actions.values():
            entry.action.add_to_hash(h)

        if (identifier := h.hexdigest()) not in states:
            return dict(
                identifier = identifier,
                entries = entries,
                actions = actions,
            )

        else:
            return None
