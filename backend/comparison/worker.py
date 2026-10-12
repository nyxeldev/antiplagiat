"""Only invoked by runner; no uploads, document text or errors go to logs."""
import json
import logging
import sys
from pathlib import Path

from .policy import ComparisonError, MAX_RESULT_BYTES
from .resources import restrict_worker


def main(directory):
    logging.disable(logging.CRITICAL)
    folder = Path(directory)
    try:
        restrict_worker()
    except Exception:
        result = ComparisonError("resource_setup", "Parser resurs chegaralarini yoqib bo‘lmadi.", 503).payload()
        result["http_status"] = 503
    else:
        try:
            from .extract import extract
            from .matching import compare
            items = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            documents = [extract(folder / item["path"], item["name"]) for item in items]
            result = compare(documents[0], documents[1:])
        except ComparisonError as error:
            result = error.payload()
            result["http_status"] = error.status
        except (MemoryError, RecursionError):
            result = ComparisonError("resource_limit", "Hujjat resurs chegarasidan oshdi.").payload()
        except Exception:
            result = ComparisonError("processing_error", "Hujjatni qayta ishlash amalga oshmadi.").payload()
    encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_RESULT_BYTES:
        encoded = json.dumps(ComparisonError("result_limit", "Hisobot hajmi chegaradan oshdi. Hujjatni kichraytiring.").payload()).encode()
    (folder / "result.json").write_bytes(encoded)


if __name__ == "__main__":
    main(sys.argv[1])
