from abc import ABC,abstractmethod
from ..util import update_hash

class Entry(ABC):
    def __init__(self, path, content, user=0, group=0, mode=None,
                 actions=None):
        self.path = path
        self.content = content
        self.user = user
        self.group = group
        self.mode = self.default_mode if mode is None else mode
        self.actions = actions or []

    @property
    @abstractmethod
    def type(self):
        pass

    @abstractmethod
    def add_to_hash(self, h):
        pass

class FileEntry(Entry):
    default_mode = 0o0644

    @property
    def type(self):
        return 'file'

    def add_to_hash(self, h):
        update_hash(
            h,
            * [ self.path,
                self.user,
                self.group,
                self.mode,
                self.content ]
            + list(self.actions)
        )

class SymlinkEntry(FileEntry):
    default_mode = 0o0755

    def __init__(self, path, target, user=0, group=0, mode=None,
                 actions=None):
        super().__init__(
            path, target.strip(),
            user=user, group=group, mode=mode,
            actions=actions,
        )

    @property
    def type(self):
        return 'symlink'

class DirEntry(Entry):
    default_mode = 0o0755

    def __init__(self, path, user=0, group=0, mode=None,
                 action=None, create_if=None):
        self.create_if = create_if
        super().__init__(
            path, None,
            user=user, group=group, mode=mode,
            actions=action,
        )

    @property
    def type(self):
        return 'dir'

    def add_to_hash(self, h):
        update_hash(h, self.path, self.user, self.group, self.mode)

__all__ = (
    'FileEntry',
    'SymlinkEntry',
    'DirEntry',
)
