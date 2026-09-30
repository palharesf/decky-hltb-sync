"""Lossless edit-data handling. No defaults for missing remote records."""
import copy
import json
from html.parser import HTMLParser


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


class _NextData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.active = dict(attrs).get('id') == '__NEXT_DATA__'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def parse_edit_html(html):
    parser = _NextData()
    parser.feed(html)
    try:
        record = json.loads(''.join(parser.parts))['props']['pageProps']['editData']
        return validate(record)
    except (ValueError, KeyError, TypeError):
        raise RecordError('Page does not contain a recognized editable record') from None
