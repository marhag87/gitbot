class GitEvent(object):
    def __init__(self, key):
        self._key = key

    def __getattr__(self, item):
        try:
            attribute = self._key.get(item)
        except AttributeError:
            attribute = None
        return attribute


class Event(GitEvent):
    @property
    def payload(self):
        return Payload(self._key.get('payload'))

    @property
    def actor(self):
        return Actor(self._key.get('actor'))

    @property
    def repo(self):
        return Repo(self._key.get('repo'))


class Payload(GitEvent):
    @property
    def issue(self):
        return Issue(self._key.get('issue'))

    @property
    def pull_request(self):
        return PullRequest(self._key.get('pull_request'))

    @property
    def comment(self):
        return Comment(self._key.get('comment'))


class Actor(GitEvent):
    pass


class Repo(GitEvent):
    pass


class Issue(GitEvent):
    pass


class PullRequest(GitEvent):
    pass


class Comment(GitEvent):
    pass
