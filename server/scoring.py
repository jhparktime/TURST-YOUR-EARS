"""Deterministic, versioned scoring. No model or reference text in the response."""
import csv
import io
import unicodedata
from collections import defaultdict

VERSION = "wer-macro-v1"
MAX_ROWS = 20000


def words(text):
    # NFKC + casefold; punctuation becomes whitespace. No number expansion.
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(" " if unicodedata.category(c).startswith("P") else c for c in text).split()


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (left != right)))
        previous = current
    return previous[-1]


def parse_submission(data):
    try:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames != ["id", "prediction"]:
            raise ValueError("CSV header must be exactly: id,prediction")
        rows = {}
        for row in reader:
            if None in row or row.get("prediction") is None:
                raise ValueError("Every row must have exactly two CSV fields.")
            identifier = row["id"].strip()
            if not identifier or identifier in rows:
                raise ValueError("IDs must be non-empty and unique.")
            if len(identifier) > 120 or len(row["prediction"]) > 4000:
                raise ValueError("An ID or prediction exceeds the size limit.")
            if len(words(row["prediction"])) > 500:
                raise ValueError("Each prediction must contain at most 500 words.")
            rows[identifier] = row["prediction"]
            if len(rows) > MAX_ROWS:
                raise ValueError("Too many rows.")
        if not rows:
            raise ValueError("The submission is empty.")
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Upload a valid UTF-8 CSV file.") from exc


def score(predictions, references):
    expected = {row["id"] for row in references}
    if set(predictions) != expected:
        raise ValueError("Submission IDs must exactly match this evaluation set (no missing or extra IDs).")
    groups = defaultdict(lambda: [0, 0, 0])
    total_cells = 0
    for row in references:
        reference = words(row["reference"])
        hypothesis = words(predictions[row["id"]])
        total_cells += len(reference) * len(hypothesis)
        if total_cells > 10_000_000:
            raise ValueError("Submission exceeds the scorer's computation limit. Contact the organizers.")
        if not reference:
            raise ValueError("Reference contains an empty normalized transcript.")
        bucket = groups[row["condition"]]
        bucket[0] += distance(reference, hypothesis)
        bucket[1] += len(reference)
        bucket[2] += 1
    conditions = {name: {"wer": 100 * errors / total, "utterances": count}
                  for name, (errors, total, count) in sorted(groups.items())}
    total_errors = sum(v[0] for v in groups.values())
    total_words = sum(v[1] for v in groups.values())
    return {"scorer": VERSION, "macro_wer": sum(v["wer"] for v in conditions.values()) / len(conditions),
            "micro_wer": 100 * total_errors / total_words, "conditions": conditions,
            "utterances": len(references)}
