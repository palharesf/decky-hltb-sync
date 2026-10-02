"""Lossless edit-data handling. No defaults for missing remote records."""
import copy
import json
import re


class RecordError(ValueError):
    pass


def validate(record):
    try:
        for key in ('userId', 'gameId', 'submissionId'):
            if type(record[key]) is not int or record[key] <= 0:
                raise ValueError()
        if not isinstance(record['platform'], str) or not record['platform']:
            raise ValueError()
        seconds(record)
    except (KeyError, TypeError, ValueError):
        raise RecordError('Unsupported record or authentication required') from None
    return record


def seconds(record):
    progress = record['general']['progress']
    values = [progress[k] for k in ('hours', 'minutes', 'seconds')]
    if any(v is not None and (type(v) is not int or v < 0) for v in values):
        raise RecordError('Unknown time format')
    h, m, s = [v or 0 for v in values]
    if m >= 60 or s >= 60:
        raise RecordError('Time out of range')
    return h * 3600 + m * 60 + s


def proposed(record, delta):
    validate(record)
    if type(delta) is not int or delta <= 0:
        raise RecordError('Session duration must be positive whole seconds')
    result = copy.deepcopy(record)
    total = seconds(record) + delta
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    result['general']['progress'].update(hours=h, minutes=m, seconds=s)
    return result


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def submission_matches(expected, actual):
    """Observed server normalization only; all user-editable fields stay strict."""
    normalized = copy.deepcopy(expected)
    # HLTB replaces its own request-IP metadata when accepting a submission.
    if 'userIp' in actual:
        normalized['userIp'] = actual['userIp']
    # An unset storefront is saved as an empty string by the current server.
    if 'storefront' in normalized and 'storefront' in actual:
        if normalized['storefront'] is None and actual['storefront'] == '':
            normalized['storefront'] = ''
    return canonical(normalized) == canonical(actual)


def creation_matches(expected, actual):
    """Only creation may omit observed empty editor defaults in the saved record."""
    normalized = copy.deepcopy(expected)
    empty_time = {'hours': None, 'minutes': None, 'seconds': None}
    defaults = {'adminId': None, 'customLabels': {'custom': '', 'custom2': '', 'custom3': ''},
                'manualTimer': {'time': empty_time}}
    for key, default in defaults.items():
        if key not in actual and key in normalized and normalized[key] == default:
            del normalized[key]
    general = normalized.get('general', {})
    if 'progressBefore' not in actual.get('general', {}) and general.get('progressBefore') == empty_time:
        del general['progressBefore']
    return submission_matches(normalized, actual)


def page_data(html):
    try:
        # Decky's frozen Python does not ship html.parser. Recognize only the
        # specific Next.js script contract, rejecting missing/ambiguous payloads.
        matches = re.findall(
            r'''<script\b[^>]*\sid\s*=\s*(["'])__NEXT_DATA__\1[^>]*>(.*?)</script\s*>''',
            html, flags=re.IGNORECASE | re.DOTALL)
        if len(matches) != 1:
            raise ValueError()
        return json.loads(matches[0][1])['props']['pageProps']
    except (ValueError, KeyError, TypeError):
        raise RecordError('Page does not contain a recognized editable record') from None


def parse_edit_html(html):
    try:
        return validate(page_data(html)['editData'])
    except (KeyError, TypeError):
        raise RecordError('Page does not contain a recognized editable record') from None
