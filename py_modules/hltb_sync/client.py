"""HLTB website adapter based on the inspected Playnite contract.

These are private website endpoints, not a supported public API. All unknown
formats fail closed. Responses and account records must never be logged.
"""
import copy
import json
import time
from .browser import IntegrationError
from .records import page_data, parse_edit_html, validate, seconds


def positive(value):
    if type(value) is not int or value <= 0:
        raise IntegrationError('invalid_identifier')
    return value


def decode(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        raise IntegrationError('unexpected_hltb_response') from None


class HLTBClient:
    def __init__(self, browser):
        self.browser = browser
        self.user_id = None

    async def identity(self):
        data = decode(await self.browser.request('/api/user'))
        try:
            user = data['data'][0]
            user_id = positive(user['user_id'])
        except (KeyError, IndexError, TypeError, IntegrationError):
            self.user_id = None
            raise IntegrationError('login_required') from None
        if self.user_id and self.user_id != user_id:
            raise IntegrationError('account_changed_disconnect_first')
        self.user_id = user_id
        return user_id

    async def library(self):
        user_id = await self.identity()
        payload = {'user_id': user_id, 'lists': ['playing', 'backlog', 'replays', 'custom',
                   'custom2', 'custom3', 'completed', 'retired'], 'set_playstyle': 'comp_all',
                   'name': '', 'platform': '', 'storefront': '', 'sortBy': '', 'sortFlip': 0,
                   'view': '', 'random': 0, 'limit': 5000, 'currentUserHome': True}
        data = decode(await self.browser.request(f'/api/user/{user_id}/games/list', payload, method='POST'))
        try:
            content = data['data']
            entries = content['gamesList']
            if not isinstance(entries, list) or type(content['total']) is not int or content['total'] != len(entries):
                raise ValueError()
            result = []
            seen = set()
            for entry in entries:
                submission = positive(entry['id'])
                if submission in seen:
                    raise ValueError()
                seen.add(submission)
                progress = entry['invested_pro']
                if type(progress) is not int or progress < 0:
                    raise ValueError()
                result.append({'submissionId': submission, 'gameId': positive(entry['game_id']),
                               'title': str(entry['custom_title']), 'platform': str(entry['platform']),
                               'seconds': progress, 'lists': [name for field, name in (
                                   ('list_playing', 'Playing'), ('list_backlog', 'Backlog'),
                                   ('list_replay', 'Replay'), ('list_comp', 'Completed'),
                                   ('list_retired', 'Retired'), ('list_custom', 'Custom'),
                                   ('list_custom2', 'Custom 2'), ('list_custom3', 'Custom 3')) if entry.get(field) == 1]})
            return result
        except (KeyError, TypeError, ValueError):
            raise IntegrationError('incomplete_or_unknown_library') from None

    async def read(self, submission_id):
        positive(submission_id)
        user_id = await self.identity()
        record = parse_edit_html(await self.browser.request(f'/submit/edit/{submission_id}'))
        if record['submissionId'] != submission_id or record['userId'] != user_id:
            raise IntegrationError('record_identity_mismatch')
        # A partial edit payload must not become a replacement submission that
        # silently resets fields missing from the current website response.
        sections = ('lists', 'general', 'singlePlayer', 'speedRuns', 'multiPlayer',
                    'review', 'additionals')
        if any(not isinstance(record.get(key), dict) for key in sections):
            raise IntegrationError('incomplete_edit_record')
        # These editor-only sections are absent from current saved records.
        # Preserve them when supplied; never synthesize fields during an update.
        if any(key in record and not isinstance(record[key], dict)
               for key in ('manualTimer', 'customLabels')):
            raise IntegrationError('incomplete_edit_record')
        return record

    async def submit(self, record):
        # Caller must durably record sending before invoking this function.
        user_id = await self.identity()
        if record['userId'] != user_id:
            raise IntegrationError('record_identity_mismatch')
        submission = record['submissionId']
        response = decode(await self.browser.request('/api/submit', record, method='POST',
                                referrer=f'/submit/edit/{submission}' if submission else '/submit'))
        if not isinstance(response, dict) or response.get('error') or response.get('success') is False:
            raise IntegrationError('submit_not_confirmed')
        # The response is never treated as proof of success. Caller MUST reread.

    async def game_identity(self, game_id):
        positive(game_id)
        try:
            page = page_data(await self.browser.request(f'/game/{game_id}'))
            games = page['game']['data']['game']
            if len(games) != 1 or games[0]['game_id'] != game_id:
                raise ValueError()
            game = games[0]
            return {'gameId': game_id, 'title': game['game_name'],
                    'steamId': str(game.get('profile_steam', '')),
                    'platforms': [p.strip() for p in game['profile_platform'].split(',')]}
        except (KeyError, TypeError, ValueError):
            raise IntegrationError('game_identity_unavailable') from None

    async def search(self, query):
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 120:
            raise IntegrationError('invalid_search')
        path = '/api/search/site'
        auth = decode(await self.browser.request(path + '/init?t=' + str(int(time.time() * 1000))))
        if not isinstance(auth, dict) or not isinstance(auth.get('token'), str):
            raise IntegrationError('search_contract_changed')
        hp_key, hp_value = auth.get('hpKey'), auth.get('hpVal')
        if bool(hp_key) != bool(hp_value) or any(v is not None and not isinstance(v, str) for v in (hp_key, hp_value)):
            raise IntegrationError('search_contract_changed')
        payload = {'searchType': 'games', 'searchTerms': query.strip().split(), 'searchPage': 1, 'size': 20,
                   'searchOptions': {'games': {'userId': 0, 'platform': '', 'sortCategory': 'name',
                    'rangeCategory': 'main', 'rangeTime': {'min': 0, 'max': 0},
                    'gameplay': {'perspective': '', 'flow': '', 'genre': '', 'difficulty': ''},
                    'modifier': 'hide_dlc'}, 'users': {}, 'filter': '', 'sort': 0, 'randomizer': 0},
                   }
        headers = {'x-auth-token': auth['token']}
        if hp_key and hp_value:
            payload[hp_key] = hp_value
            headers.update({'x-hp-key': hp_key, 'x-hp-val': hp_value})
        response = decode(await self.browser.request(path, payload, method='POST', headers={
            **headers}))
        try:
            rows = response['data']
            if not isinstance(rows, list):
                raise ValueError()
            return [{'gameId': positive(r['game_id']), 'title': str(r['game_name']),
                     'main': r.get('comp_main', 0), 'extra': r.get('comp_plus', 0),
                     'completionist': r.get('comp_100', 0)} for r in rows]
        except (KeyError, TypeError, ValueError):
            raise IntegrationError('search_contract_changed') from None


def new_record(user_id, game_id, title, platform):
    """Minimal full submission model mirrored from the reference's default model."""
    positive(user_id)
    positive(game_id)
    if not all(isinstance(v, str) and 0 < len(v.strip()) <= 200 for v in (title, platform)):
        raise IntegrationError('invalid_game')
    empty_time = {'hours': None, 'minutes': None, 'seconds': None}
    date = {'year': '0000', 'month': '00', 'day': '00'}
    timed = lambda: {'time': copy.deepcopy(empty_time), 'notes': ''}
    return {'submissionId': 0, 'userId': user_id, 'userName': None, 'userIp': None,
            'gameId': game_id, 'title': title, 'platform': platform, 'storefront': '',
            'lists': {k: k == 'playing' for k in ['playing', 'backlog', 'replay', 'custom',
                                               'custom2', 'custom3', 'completed', 'retired']},
            'general': {'progress': {'hours': 0, 'minutes': 0, 'seconds': 0},
                        'progressBefore': copy.deepcopy(empty_time), 'retirementNotes': '',
                        'startDate': copy.deepcopy(date), 'completionDate': copy.deepcopy(date)},
            'singlePlayer': {'playCount': False, 'includesDLC': False, 'compMain': timed(),
                             'compPlus': timed(), 'comp100': timed()},
            'speedRuns': {'percAny': timed(), 'perc100': timed()},
            'multiPlayer': {'coOp': {'time': copy.deepcopy(empty_time)}, 'vs': {'time': copy.deepcopy(empty_time)}},
            'review': {'score': 0, 'notes': ''}, 'additionals': {'notes': '', 'video': ''},
            'manualTimer': {'time': copy.deepcopy(empty_time)}, 'adminId': None,
            'customLabels': {'custom': '', 'custom2': '', 'custom3': ''}}


def summary(record):
    validate(record)
    return {'submissionId': record['submissionId'], 'gameId': record['gameId'],
            'title': record.get('title', ''), 'platform': record['platform'],
            'seconds': seconds(record), 'lists': record.get('lists', {})}
