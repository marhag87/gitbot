"""
Gitbot
"""
import requests
import json
from datetime import datetime


def events(user, repo):
    response = requests.get(
        'https://api.github.com/repos/{}/{}/events'.format(
            user,
            repo,
        )
    )
    if response.status_code == 200:
        return {
            'ETag': response.headers.get('ETag'),
            'X-RateLimit-Limit': response.headers.get('X-RateLimit-Limit'),
            'X-RateLimit-Remaining': response.headers.get('X-RateLimit-Remaining'),
            'X-RateLimit-Reset': response.headers.get('X-RateLimit-Reset'),
            'body': json.loads(response.text)
        }
    else:
        return None


def new_events(repo):
    my_new_events = []
    all_events = events(
        repo.get('user'),
        repo.get('repo'),
    )
    if all_events is None:
        return ([], repo)

    latest = repo.get('latest')
    repo_etag = repo.get('ETag')
    etag = all_events.get('ETag')
    if repo_etag is None or repo_etag != etag:
        repo['ETag'] = etag
        for event in reversed(all_events.get('body')):
            updated_at = datetime.strptime(event.get('created_at'), '%Y-%m-%dT%H:%M:%SZ')
            if latest is None or updated_at >= latest:
                latest = updated_at
                my_new_events.append(event)
        repo['latest'] = latest

    return (my_new_events, repo)


def parse_event(event):
    event_type = event.get('type')

    if event_type == 'PullRequestEvent':
        return (
            'New pull request from {user}:\n'
            '{url}'.format(
                user=event.get('actor', {}).get('login'),
                url=event.get('payload', {}).get('pull_request', {}).get('html_url'),
            ))

    elif event_type == 'PushEvent':
        message = ['New code has been pushed:', '```']
        for commit in reversed(event.get('payload').get('commits')):
            message.append(
                commit.get('message').split('\n\n')[0]  # First line of commit message
            )
        message.append('```')
        return "\n".join(message)

    elif event_type == 'IssueCommentEvent':
        return (
            'New comment from {user}:\n'
            '```\n'
            '{comment}\n'
            '```'.format(
                user=event.get('actor', {}).get('display_login'),
                comment=event.get('payload', {}).get('comment', {}).get('body'),
            )
        )

    else:
        return "Event not implemented: {}".format(event_type)
