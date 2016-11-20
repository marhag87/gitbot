from pprint import pprint
import asyncio
import discord
from gitbot import (
    events,
    new_events,
    parse_event,
)
from pyyamlconfig import (
    load_config,
    write_config,
    PyYAMLConfigError,
)


class BotError(Exception):
    pass


_CONFIGFILE = 'config.yaml'
_CLIENT = discord.Client()
_SLEEPTIME = 5
try:
    _CONFIG = load_config(_CONFIGFILE)
except PyYAMLConfigError:
    _CONFIG = {}


@_CLIENT.event
async def on_ready():
    """
    Print user information once logged in
    """
    print('Logged in as')
    print(_CLIENT.user.name)
    print(_CLIENT.user.id)
    print('------')
    perms = discord.Permissions.none()
    perms.read_messages = True
    perms.send_messages = True
    print(discord.utils.oauth_url(_CONFIG.get('clientid'), permissions=perms))


@_CLIENT.event
async def on_message(message):
    if _CLIENT.user in message.mentions:
        if message.content.startswith('<@{}> register'.format(_CLIENT.user.id)):
            full_repo = message.content.split(' ')[-1]
            if full_repo == 'register':
                content = 'You need to specify a repo'
            else:
                try:
                    add_repo(full_repo, message.channel.id)
                    content = 'Added repo {}'
                except BotError as err:
                    content = 'Could not add repo, {}'.format(
                        err,
                    )
            await _CLIENT.send_message(
                message.channel,
                content.format(full_repo),
            )
        else:
            content = [
                '```',
                'Usage:',
                '  @gitbot register REPO [EVENT]...',
                '    Register a repo for updates, by default all events will trigger an update',
                '  @gitbot unregister REPO',
                '    Unregister a repo',
                '  @gitbot list',
                '    List repos that are registered',
                '',
                'REPO should be in the form USERNAME/REPOSITORY',
                '```',
            ]
            await _CLIENT.send_message(
                message.channel,
                "\n".join(content),
            )


def add_repo(full_repo, channel):
    try:
        user = full_repo.split('/')[0]
        repo = full_repo.split('/')[1]
    except IndexError:
        raise BotError('not a valid repo format')
    if not isinstance(events(user, repo), dict):
        raise BotError('it does not exist')
    repo_exists = False
    for config_repo in _CONFIG.get('repos', []):
        if config_repo.get('user') == user and config_repo.get('repo') == repo:
            repo_exists = True
            if channel in config_repo.get('channels'):
                raise BotError('repo already added')
            else:
                config_repo['channels'].append(channel)

    if not repo_exists:
        if _CONFIG.get('repos') is None:
            _CONFIG['repos'] = []
        _CONFIG['repos'].append(
            {
                'user': user,
                'repo': repo,
                'channels': [channel]
            }
        )

    write_config(
        _CONFIGFILE,
        _CONFIG,
    )
    reset_etag()


def reset_etag():
    pass


def out(message):
    print(message)
    print('-------------------------')


async def main_loop():
    await _CLIENT.wait_until_ready()
    while not _CLIENT.is_closed:
        await asyncio.sleep(_SLEEPTIME)
        new_config = {
            'token': _CONFIG.get('token'),
            'clientid': _CONFIG.get('clientid'),
            'repos': [],
        }
        for repo in _CONFIG.get('repos', []):
            (events, repo) = new_events(repo)
            new_config['repos'].append(repo)
            for event in events:
                if event.get('type') in repo.get('events', []) or repo.get('events') is None:
                    for channel in repo.get('channels'):
                        message = parse_event(event)
                        await _CLIENT.send_message(
                            _CLIENT.get_channel(channel),
                            message,
                        )

        write_config(
            _CONFIGFILE,
            new_config,
        )

_CLIENT.loop.create_task(main_loop())
_CLIENT.run(_CONFIG.get('token'))
