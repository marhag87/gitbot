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
    elif response.status_code == 404:
        raise GitbotError('repo does not exist')
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


def handle_pull_request_event(event):
    """
    Handle PullRequestEvent
    """
    if event.payload.action == 'opened':
        message = 'New pull request from {user}:\n{url}'
    elif event.payload.action == 'closed':
        if event.payload.pull_request.merged:
            message = 'Merged Pull request #{pull_request} ({title}) in {repo}'
        else:
            message = 'Pull request #{pull_request} ({title}) closed for {repo}'
    elif event.payload.action == 'reopened':
        message = 'Pull request #{pull_request} ({title}) reopened for {repo}'
    else:
        message = 'Action {action} for event {type} not implemented'
    return message


def handle_push_event(event):
    """
    Handle PushEvent
    """
    full_message = [
        'New code has been pushed to {repo}, {ref} branch:',
        '```',
    ]
    for commit in reversed(event.payload.commits):
        comment = commit.get('message').split('\n\n')[0]  # First line of commit message
        comment = comment.replace('{', '{{')  # Clean up comments so that they don't get formated
        comment = comment.replace('}', '}}')
        full_message.append(
            comment,
        )
    full_message.append('```')
    return '\n'.join(full_message)


def handle_issue_comment_event():
    """
    Handle IssueCommentEvent
    """
    return (
        'New comment from {user} in Pull Request #{issue_number} ({issue_title}) for {repo}:\n'
        '```\n'
        '{comment}\n'
        '```\n'
    )


def handle_create_event(event):
    """
    Handle CreateEvent
    """
    if event.payload.ref_type == 'branch':
        message = 'Branch {branch} created in repo {repo}'
    elif event.payload.ref_type == 'repository':
        message = 'Repository created: {repo}'
    else:
        message = 'CreateEvent not implemented for ref_type {ref_type}'
    return message


def handle_delete_event(event):
    """
    Handle DeleteEvent
    """
    if event.payload.ref_type == 'branch':
        message = 'Branch {branch} deleted from repo {repo}'
    else:
        message = 'DeleteEvent not implemented for ref_type {ref_type}'
    return message


def parse_event(event):
    """
    Parse an event, return some text for printing
    """
    my_event = Event(event)
    if my_event.type == 'PullRequestEvent':
        message = handle_pull_request_event(my_event)
    elif my_event.type == 'PushEvent':
        message = handle_push_event(my_event)
    elif my_event.type == 'IssueCommentEvent':
        message = handle_issue_comment_event()
    elif my_event.type == 'CreateEvent':
        message = handle_create_event(my_event)
    elif my_event.type == 'DeleteEvent':
        message = handle_delete_event(my_event)
    else:
        message = 'Event not implemented: {type}'

    return message.format(
        user=my_event.actor.display_login,
        url=my_event.payload.pull_request.html_url,
        pull_request=my_event.payload.pull_request.number,
        title=my_event.payload.pull_request.title,
        repo=my_event.repo.name,
        action=my_event.payload.action,
        type=my_event.type,
        ref=my_event.payload.ref,
        ref_type=my_event.payload.ref_type,
        issue_number=my_event.payload.issue.number,
        issue_title=my_event.payload.issue.title,
        comment=my_event.payload.comment.body,
        branch=my_event.payload.ref,
    )
