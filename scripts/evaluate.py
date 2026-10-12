"""Score local predictions with exactly the web evaluator's protocol."""
import argparse
import json
from pathlib import Path
from server.scoring import parse_submission, score, validate_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        refs = validate_manifest(json.loads(args.references.read_text(encoding='utf-8')))
        result = score(parse_submission(args.predictions.read_bytes()), refs)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')


if __name__ == '__main__':
    main()
