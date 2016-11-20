"""
Gitbot
"""
import requests
import json
from datetime import datetime


class GitbotError(Exception):
    pass


def events(user, repo, etag=None):
    response = requests.get(
        'https://api.github.com/rate_limit',
    )
    if response.headers.get('X-RateLimit-Remaining') == '0':
        raise GitbotError('Out of ratelimit tokens')

    if etag is not None:
        headers = {'If-None-Match': etag}
    else:
        headers = {}
    response = requests.get(
        'https://api.github.com/repos/{}/{}/events'.format(
            user,
            repo,
        ),
        headers=headers,
    )
    if response.status_code == 200:
        return {
            'ETag': response.headers.get('ETag'),
            'X-RateLimit-Limit': response.headers.get('X-RateLimit-Limit'),
            'X-RateLimit-Remaining': response.headers.get('X-RateLimit-Remaining'),
            'X-RateLimit-Reset': response.headers.get('X-RateLimit-Reset'),
            'body': json.loads(response.text)
        }
    if response.status_code == 304:
        return None  # 304 = Not modified
    else:
        if response.headers.get('X-RateLimit-Remaining') == '0':
            raise GitbotError('Out of ratelimit tokens')
        else:
            raise GitbotError('Unknown error, status code {}'.format(
                response.status_code,
            ))


def new_events(repo):
    my_new_events = []
    all_events = events(
        repo.get('user'),
        repo.get('repo'),
        repo.get('ETag'),
    )
    if all_events is None:
        return [], repo

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

    return my_new_events, repo


def parse_event(event):
    event_type = event.get('type')

    if event_type == 'PullRequestEvent':
        action = event.get('payload', {}).get('action')
        if action == 'opened':
            return (
                'New pull request from {user}:\n'
                '{url}'.format(
                    user=event.get('actor', {}).get('login'),
                    url=event.get('payload', {}).get('pull_request', {}).get('html_url'),
                ))
        elif action == 'closed':
            if event.get('payload', {}).get('pull_request', {}).get('merged'):
                return (
                    'Merged pull request:\n'
                    '{url}'.format(
                        url=event.get('payload', {}).get('pull_request', {}).get('html_url'),
                    )
                )
            else:
                return (
                    'Pull request closed:\n'
                    '{url}'.format(
                        url=event.get('payload', {}).get('pull_request', {}).get('html_url'),
                    )
                )
        else:
            return "Action {} for event {} not implemented".format(
                action,
                event_type,
            )

    elif event_type == 'PushEvent':
        message = [
            'New code has been pushed to {repo}:'.format(
                repo=event.get('repo', {}).get('name'),
            ),
            '```',
        ]
        for commit in reversed(event.get('payload').get('commits')):
            message.append(
                commit.get('message').split('\n\n')[0]  # First line of commit message
            )
        message.append('```')
        return "\n".join(message)

    elif event_type == 'IssueCommentEvent':
        return (
            'New comment from {user} in {repo}:\n'
            '```\n'
            '{comment}\n'
            '```'.format(
                user=event.get('actor', {}).get('display_login'),
                repo=event.get('repo', {}).get('name'),
                comment=event.get('payload', {}).get('comment', {}).get('body'),
            )
        )

    else:
        return "Event not implemented: {}".format(event_type)
