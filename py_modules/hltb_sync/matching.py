"""Conservative suggestions only. A match never authorizes an account write."""
import re


def normalized(value):
    return ' '.join(re.findall(r'\w+', value.casefold()))


def trackable(app):
    name = normalized(app['name'])
    blocked = ('es de', 'emulationstation', 'nested desktop', 'desktop mode',
               'heroic', 'lutris', 'emudeck', 'retroarch', 'pcsx2', 'dolphin')
    return not app.get('excluded', False) and not any(
        name == label or name.startswith(label + ' ') for label in blocked)


def suggest(app, entries):
    title = normalized(app['name'])
    tokens = set(title.split())
    platform = app.get('platform') or ('PC' if app['steam'] else None)
    ranked = []
    for entry in entries:
        other = normalized(entry['title'])
        exact = title == other
        words = set(other.split())
        similarity = len(tokens & words) / max(1, len(tokens | words))
        if not exact and similarity < 0.5:
            continue
        same_platform = bool(platform) and normalized(platform) == normalized(entry['platform'])
        strong = exact and same_platform
        score = (100 if exact else similarity * 60) + (30 if same_platform else 0)
        reason = 'Title + platform' if strong else 'Same title' if exact else 'Similar title'
        ranked.append((score, strong, {**entry, 'reason': reason}))
    ranked.sort(key=lambda item: (-item[0], item[2]['submissionId']))
    strong = [item for item in ranked if item[1]]
    recommended = strong[0][2]['submissionId'] if len(strong) == 1 else None
    return [item[2] for item in ranked[:5]], recommended
