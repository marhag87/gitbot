"""
Gitbot
"""
import asyncio
import discord
from gitbot import (
    events,
    new_events,
    parse_event,
    GitbotError,
)
from pyyamlconfig import (
    load_config,
    write_config,
    PyYAMLConfigError,
)


class BotError(Exception):
    """
    Generic Bot Error
    """
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
    """
    Handle messages that are posted in a channel
    """
    if _CLIENT.user in message.mentions:
        if message.content.startswith('<@{}> add'.format(_CLIENT.user.id)):
            full_repo = message.content.split(' ')[-1]
            if full_repo == 'add':
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
        elif message.content.startswith('<@{}> remove'.format(_CLIENT.user.id)):
            full_repo = message.content.split(' ')[-1]
            if full_repo == 'remove':
                content = 'You need to specify a repo'
            else:
                try:
                    remove_repo(full_repo, message.channel.id)
                    content = 'Removed repo {}'
                except BotError as err:
                    content = 'Could not remove repo, {}'.format(
                        err,
                    )
            await _CLIENT.send_message(
                message.channel,
                content.format(full_repo),
            )
        elif message.content.startswith('<@{}> list'.format(_CLIENT.user.id)):
            content = ['The following repos are active in this channel:']
            repos = list_repos(message.channel.id)
            if repos:
                content += repos
            else:
                content = ['There are not repos active in this channel']
            await _CLIENT.send_message(
                message.channel,
                '\n'.join(content),
            )
        else:
            content = [
                '```',
                'Usage:',
                '  @gitbot add REPO [EVENT]...',
                '    Register a repo for updates, by default all events will trigger an update',
                '  @gitbot remove REPO',
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
    """
    Add a repo, write config to file and update ETag and latest
    """
    try:
        user = full_repo.split('/')[0]
        repo = full_repo.split('/')[1]
    except IndexError:
        raise BotError('not a valid repo format')
    try:
        if not isinstance(events(user, repo), dict):
            raise BotError('it does not exist')
    except GitbotError as err:
        raise BotError(err)
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
    fetch_updates()


def remove_repo(full_repo, channel):
    """
    Remove a repo, write config to file
    """
    try:
        user = full_repo.split('/')[0]
        repo = full_repo.split('/')[1]
    except IndexError:
        raise BotError('not a valid repo format')
    for config_repo in _CONFIG.get('repos', []):
        if config_repo.get('user') == user \
                and config_repo.get('repo') == repo \
                and channel in config_repo.get('channels'):
            if config_repo.get('channels') == [channel]:
                _CONFIG['repos'] = [
                    x
                    for
                    x
                    in
                    _CONFIG.get('repos')
                    if not (x.get('user') == user and x.get('repo') == repo)
                    ]
            else:
                config_repo['channels'].remove(channel)

    write_config(
        _CONFIGFILE,
        _CONFIG,
    )


def list_repos(channel):
    """
    Return a list of repos that are active for a channel
    """
    return [
        '{}/{}'.format(x.get('user'), x.get('repo'))
        for
        x
        in _CONFIG.get('repos', [])
        if channel in x.get('channels')
        ]


def fetch_updates():
    """
    Fetch all changes that have happened for repos
    """
    content = []
    new_config = {
        'token': _CONFIG.get('token'),
        'clientid': _CONFIG.get('clientid'),
        'github-token': _CONFIG.get('github-token'),
        'repos': [],
    }
    try:
        for repo in _CONFIG.get('repos', []):
            (newevents, repo) = new_events(repo, token=_CONFIG.get('github-token'))
            new_config['repos'].append(repo)
            for event in newevents:
                if event.get('type') in repo.get('events', []) or repo.get('events') is None:
                    for channel in repo.get('channels'):
                        content.append(
                            {
                                'message': parse_event(event),
                                'channel': channel,
                            }
                        )

        write_config(
            _CONFIGFILE,
            new_config,
        )
        return content
    except GitbotError as err:
        print('Could not fetch events: {}'.format(err))


async def main_loop():
    """
    Main loop that listens for changes and prints them to relevant channels
    """
    await _CLIENT.wait_until_ready()
    while not _CLIENT.is_closed:
        await asyncio.sleep(_SLEEPTIME)
        for content in fetch_updates():
            message = content.get('message')
            if message is not None:
                await _CLIENT.send_message(
                    _CLIENT.get_channel(content.get('channel')),
                    message,
                )


fetch_updates()
_CLIENT.loop.create_task(main_loop())
_CLIENT.run(_CONFIG.get('token'))
