from gitbot import (
    new_events,
    parse_event,
)
from pyyamlconfig import (
    load_config,
    write_config,
    PyYAMLConfigError,
)
_CONFIGFILE = 'config.yaml'


def out(message):
    print(message)


def main():
    try:
        config = load_config(_CONFIGFILE)
    except PyYAMLConfigError:
        config = {}

    new_config = {'repos': []}
    changed = False
    for repo in config.get('repos'):
        (events, repo) = new_events(repo)
        if events:
            changed = True
            new_config['repos'].append(repo)
        for event in events:
            if event.get('type') in repo.get('events') or repo.get('events') == ['all']:
                out(parse_event(event))

    if changed is True:
        out('Changed')
        write_config(
            _CONFIGFILE,
            new_config,
        )
    else:
        out('Not changed')

if __name__ == '__main__':
    main()
