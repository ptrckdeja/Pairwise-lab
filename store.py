"""SQLite persistence and blind comparison rules, independent of HTTP."""
import json
import secrets
import sqlite3
from datetime import datetime, timezone

CRITERIA = ('correctness', 'clarity', 'instruction_following')


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def initialize(path):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS comparisons (
          id INTEGER PRIMARY KEY, prompt TEXT NOT NULL, category TEXT NOT NULL,
          model_a TEXT NOT NULL, response_a TEXT NOT NULL,
          model_b TEXT NOT NULL, response_b TEXT NOT NULL,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews (
          comparison_id INTEGER PRIMARY KEY REFERENCES comparisons(id),
          preference TEXT NOT NULL CHECK(preference IN ('a','b','tie','neither')),
          scores TEXT NOT NULL, reason TEXT NOT NULL, reviewed_at TEXT NOT NULL);
        ''')


def text(value, field, maximum=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{field} must be nonempty text, at most {maximum} characters')
    return value.strip()


def validate_comparison(item):
    if not isinstance(item, dict):
        raise ValueError('Each comparison must be an object')
    out = {key: text(item.get(key), key, 200 if key.startswith('model_') or key == 'category' else 20000)
           for key in ('prompt', 'category', 'model_a', 'response_a', 'model_b', 'response_b')}
    if out['model_a'] == out['model_b']:
        raise ValueError('Use distinct model names or versions')
    # Randomize once on ingestion; labels stay stable across reloads and reviews.
    if secrets.randbelow(2):
        out['model_a'], out['model_b'] = out['model_b'], out['model_a']
        out['response_a'], out['response_b'] = out['response_b'], out['response_a']
    return out


def ingest(path, items):
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ValueError('Import must contain between 1 and 100 comparisons')
    validated = [validate_comparison(item) for item in items]
    with connect(path) as db:
        for item in validated:
            db.execute('INSERT INTO comparisons(prompt,category,model_a,response_a,model_b,response_b,created_at) VALUES(?,?,?,?,?,?,?)',
                       (*item.values(), datetime.now(timezone.utc).isoformat()))
    return len(validated)


def queue(path):
    with connect(path) as db:
        return [dict(row) for row in db.execute('''SELECT c.id,c.prompt,c.category,
          CASE WHEN r.comparison_id IS NULL THEN 0 ELSE 1 END AS reviewed
          FROM comparisons c LEFT JOIN reviews r ON c.id=r.comparison_id ORDER BY c.id''')]


def comparison(path, identifier):
    with connect(path) as db:
        row = db.execute('SELECT * FROM comparisons WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise LookupError('Comparison not found')
        result = dict(row)
        review = db.execute('SELECT * FROM reviews WHERE comparison_id=?', (identifier,)).fetchone()
        if review:
            result['review'] = dict(review)
            result['review']['scores'] = json.loads(review['scores'])
        else:
            result.pop('model_a')
            result.pop('model_b')
        return result


def review(path, identifier, item):
    if not isinstance(item, dict) or item.get('preference') not in ('a', 'b', 'tie', 'neither'):
        raise ValueError('Choose A, B, tie, or neither')
    reason = text(item.get('reason'), 'reason', 4000)
    scores = item.get('scores')
    if not isinstance(scores, dict) or set(scores) != {'a', 'b'}:
        raise ValueError('Scores are required for A and B')
    for side in ('a', 'b'):
        if not isinstance(scores[side], dict) or set(scores[side]) != set(CRITERIA):
            raise ValueError('Score all three criteria for each response')
        if any(type(v) is not int or not 1 <= v <= 5 for v in scores[side].values()):
            raise ValueError('Scores must be integers from 1 to 5')
    with connect(path) as db:
        if not db.execute('SELECT 1 FROM comparisons WHERE id=?', (identifier,)).fetchone():
            raise LookupError('Comparison not found')
        # Immutable reviews prevent silently overwriting a blinded judgment after reveal.
        try:
            db.execute('INSERT INTO reviews VALUES(?,?,?,?,?)',
                       (identifier, item['preference'], json.dumps(scores), reason, datetime.now(timezone.utc).isoformat()))
        except sqlite3.IntegrityError as exc:
            raise FileExistsError('This comparison already has a saved review') from exc
    return comparison(path, identifier)


def export(path):
    return [comparison(path, row['id']) for row in queue(path) if row['reviewed']]


def summary(path):
    rows = export(path)
    models = {}
    for row in rows:
        for side in ('a', 'b'):
            name = row['model_' + side]
            stats = models.setdefault(name, {'appearances': 0, 'wins': 0, 'ties': 0, 'neither': 0, 'score_sum': 0})
            stats['appearances'] += 1
            stats['wins'] += row['review']['preference'] == side
            stats['ties'] += row['review']['preference'] == 'tie'
            stats['neither'] += row['review']['preference'] == 'neither'
            stats['score_sum'] += sum(row['review']['scores'][side].values())
    for stats in models.values():
        stats['mean_score'] = round(stats.pop('score_sum') / (stats['appearances'] * len(CRITERIA)), 2)
    return {'total': len(queue(path)), 'reviewed': len(rows), 'models': models}
