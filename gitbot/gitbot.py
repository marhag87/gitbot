"""
Helper library for handling git events
"""
import json
import requests
from gitbot.event import Event


class GitbotError(Exception):
    """
    Generic Gitbot Error
    """
    pass


def events(user, repo, etag=None, token=None):
    """
    Fetch all events for a repo
    Because of rate limits, etag is used to not fetch data if nothing has changed
    """
    if token is not None:
        headers = {
            'Authorization': 'token {}'.format(token)
        }
    else:
        headers = {}
    response = requests.get(
        'https://api.github.com/rate_limit',
        headers=headers,
    )
    if response.headers.get('X-RateLimit-Remaining') == '0':
        raise GitbotError('Out of ratelimit tokens')

    if etag is not None:
        headers['If-None-Match'] = etag
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


def new_events(repo, token=None):
    """
    Fetch all new events for a repo
    """
    my_new_events = []
    all_events = events(
        repo.get('user'),
        repo.get('repo'),
        etag=repo.get('ETag'),
        token=token,
    )
    if all_events is None:
        return [], repo

    latest = repo.get('latest')
    repo_etag = repo.get('ETag')
    etag = all_events.get('ETag')
    if repo_etag is None or repo_etag != etag:
        repo['ETag'] = etag
        for event in reversed(all_events.get('body')):
            if latest is None or int(event.get('id')) > int(latest):
                latest = event.get('id')
                my_new_events.append(event)
        repo['latest'] = latest

    return my_new_events, repo


def parse_event(event):
    """
    Parse an event, return some text for printing
    """
    my_event = Event(event)
    if my_event.type == 'PullRequestEvent':
        if my_event.payload.action == 'opened':
            return (
                'New pull request from {user}:\n'
                '{url}'.format(
                    user=my_event.actor.login,
                    url=my_event.payload.pull_request.html_url,
                ))
        elif my_event.payload.action == 'closed':
            if my_event.payload.pull_request.merged:
                return (
                    'Merged pull request:\n'
                    '{url}'.format(
                        url=my_event.payload.pull_request.html_url,
                    )
                )
            else:
                return (
                    'Pull request #{pull_request} ({title}) closed for {repo}'.format(
                        pull_request=my_event.payload.pull_request.number,
                        title=my_event.payload.pull_request.title,
                        repo=my_event.repo.name,
                    )
                )
        elif my_event.payload.action == 'reopened':
            return (
                'Pull request #{pull_request} ({title}) reopened for {repo}'.format(
                    pull_request=my_event.payload.pull_request.number,
                    title=my_event.payload.pull_request.title,
                    repo=my_event.repo.name,
                )
            )
        else:
            return "Action {} for event {} not implemented".format(
                my_event.payload.action,
                my_event.type,
            )

    elif my_event.type == 'PushEvent':
        message = [
            'New code has been pushed to {repo} {ref}:'.format(
                repo=my_event.repo.name,
                ref=my_event.payload.ref,
            ),
            '```',
        ]
        for commit in reversed(my_event.payload.commits):
            message.append(
                commit.get('message').split('\n\n')[0]  # First line of commit message
            )
        message.append('```')
        return "\n".join(message)

    elif my_event.type == 'IssueCommentEvent':
        return (
            'New comment from {user} in Pull Request #{pull_request} ({title}) for {repo}:\n'
            '```\n'
            '{comment}\n'
            '```'.format(
                user=my_event.actor.display_login,
                pull_request=my_event.payload.issue.number,
                title=my_event.payload.issue.title,
                repo=my_event.repo.name,
                comment=my_event.payload.comment.body,
            )
        )

    elif my_event.type == 'CreateEvent':
        if my_event.payload.ref_type == 'branch':
            return (
                'Branch {branch} created in repo {repo}'.format(
                    branch=my_event.payload.ref,
                    repo=my_event.repo.name,
                )
            )
        elif my_event.payload.ref_type == 'repository':
            return (
                'Repository created: {repo}'.format(
                    repo=my_event.repo.name,
                )
            )
        else:
            return 'CreateEvent not implemented for ref_type {ref_type}'.format(
                ref_type=my_event.payload.ref_type,
            )

    elif my_event.type == 'DeleteEvent':
        if my_event.payload.ref_type == 'branch':
            return (
                'Branch {branch} deleted from repo {repo}'.format(
                    branch=my_event.payload.ref,
                    repo=my_event.repo.name,
                )
            )
        else:
            return 'DeleteEvent not implemented for ref_type {ref_type}'.format(
                ref_type=my_event.payload.ref_type,
            )

    else:
        return "Event not implemented: {type}".format(
            type=my_event.type,
        )
