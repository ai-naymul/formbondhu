"""End-to-end evaluation: every rule card, clean and with its three demo mistakes, as a crisp render and as a
degraded "phone photo", sent through the live /api/check exactly like the app does.

Usage: python eval/run_eval.py [--set rendered|handwriting] [--base http://localhost:8000] [--workers 3]
"rendered" needs eval/rendered.json (Form maker renders exported from the browser); "handwriting" uses the
handwritten letters in eval/handwriting/ with their expected results in eval/handwriting/expected.json.
Both need a running server.
"""
import argparse
import base64
import copy
import io
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.rules import audit, load_cards  # noqa: E402

EVAL = ROOT / "eval"
IMAGES = EVAL / "images"


def expected_flags(card, variant):
    """Ground truth from the rule engine itself: a perfect read of the form, with the card's demo mistakes applied."""
    if variant == "clean":
        return set()
    e = {"fields": [{"label_en": f["label_en"], "label_bn": f["label_bn"], "value": f["sample"], "is_empty": False}
                    for f in card["fields"]],
         "signature_boxes": [{"label": s["label_en"], "has_ink": True} for s in card["signatures"]],
         "photo_box": {"present": card["photo_required"], "filled": card["photo_required"]}}
    demo = card["demo_mistakes"]
    by_key = {f["key"]: f["label_en"] for f in card["fields"]}
    for key, value in demo.get("set", {}).items():
        for f in e["fields"]:
            if f["label_en"] == by_key[key]:
                f["value"], f["is_empty"] = value, value == ""
    if demo.get("clear_signature"):
        label = next(s["label_en"] for s in card["signatures"] if s["key"] == demo["clear_signature"])
        next(b for b in e["signature_boxes"] if b["label"] == label)["has_ink"] = False
    if demo.get("photo_off"):
        e["photo_box"]["filled"] = False
    return {f["rule_id"] for f in audit(card, copy.deepcopy(e))[0]}


def phone_photo(png_bytes):
    """Simulate a quick phone snapshot: slight tilt, soft focus, smaller and heavily compressed."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img = img.rotate(3.5, expand=True, fillcolor=(214, 206, 190), resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(1.1))
    img.thumbnail((1100, 1100))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=55)
    return out.getvalue()


def build_cases():
    IMAGES.mkdir(parents=True, exist_ok=True)
    cards = load_cards()
    cases = []
    for item in json.loads((EVAL / "rendered.json").read_text()):
        png = base64.b64decode(item["png"].split(",", 1)[1])
        card = cards[item["card"]]
        expected = expected_flags(card, item["variant"])
        for quality, data, mime, ext in (("crisp", png, "image/png", "png"), ("phone", phone_photo(png), "image/jpeg", "jpg")):
            path = IMAGES / f"{item['card']}__{item['variant']}__{quality}.{ext}"
            path.write_bytes(data)
            cases.append({"card": item["card"], "kind": card["kind"], "variant": item["variant"], "quality": quality,
                          "path": path, "mime": mime, "expected": expected})
    return cases


def build_handwriting_cases():
    cards = load_cards()
    manifest = json.loads((EVAL / "handwriting" / "expected.json").read_text())
    return [{"card": spec["card"], "kind": cards[spec["card"]]["kind"],
             "variant": "clean" if not spec["expected"] else "mistakes", "quality": name.split("__")[1].removesuffix(".png"),
             "path": EVAL / "handwriting" / name, "mime": "image/png", "expected": set(spec["expected"])}
            for name, spec in manifest.items() if not name.startswith("_")]


def run_case(base, case):
    started = time.perf_counter()
    result, error, draft_check = None, None, None
    try:
        with httpx.Client(timeout=120) as client:
            files = {"image": (case["path"].name, case["path"].read_bytes(), case["mime"])}
            with client.stream("POST", f"{base}/api/check", files=files) as resp:
                if resp.status_code != 200:
                    error = f"HTTP {resp.status_code}: {resp.read().decode()[:200]}"
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    if event["type"] == "result":
                        result = event
                    elif event["type"] == "error":
                        error = event["message"][:200]
                    elif event["type"] == "step" and event["id"] == "draft" and event["status"] == "done":
                        draft_check = event["output"].get("grounding_check")
    except httpx.HTTPError as exc:
        error = str(exc)[:200]
    seconds = time.perf_counter() - started
    if result is None:
        return {**case, "error": error or "no result", "seconds": seconds}
    flagged = {p["rule_id"] for p in result.get("problems", [])}
    manual = {p["rule_id"] for p in result.get("manual", [])}
    matched = (result.get("card") or {}).get("id")
    return {**case, "status": result["status"], "matched": matched, "flagged": flagged, "manual": manual,
            "seconds": seconds, "draft_check": draft_check, "has_draft": bool(result.get("draft"))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--set", choices=["rendered", "handwriting"], default="rendered")
    parser.add_argument("--tag", default="", help="suffix for the results file, e.g. 'live' for the deployed site")
    args = parser.parse_args()
    cases = build_cases() if args.set == "rendered" else build_handwriting_cases()
    print(f"{len(cases)} cases, {args.workers} at a time", flush=True)
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda c: run_case(args.base, c), cases))

    rows, exact, card_ok = [], 0, 0
    tp = fp = fn = 0
    for r in results:
        name = f"{r['card']} / {r['variant']} / {r['quality']}"
        if "error" in r:
            rows.append(f"| {name} | ERROR | {r['error']} | | {r['seconds']:.0f}s |")
            fn += len(r["expected"])
            continue
        card_ok += r["matched"] == r["card"]
        hit, wrong, missed = r["flagged"] & r["expected"], r["flagged"] - r["expected"], r["expected"] - r["flagged"]
        tp, fp, fn = tp + len(hit), fp + len(wrong), fn + len(missed)
        ok = r["flagged"] == r["expected"] and r["matched"] == r["card"]
        exact += ok
        note = []
        if r["matched"] != r["card"]:
            note.append(f"matched {r['matched']}")
        if missed:
            note.append("missed " + ",".join(sorted(missed)) + (f" (in check-yourself: {','.join(sorted(missed & r['manual']))})" if missed & r["manual"] else ""))
        if wrong:
            note.append("false alarm " + ",".join(sorted(wrong)))
        if r["kind"] == "letter" and r["variant"] == "mistakes":
            note.append(f"draft {'ok, ' + str(r['draft_check']) if r['has_draft'] else 'missing'}")
        rows.append(f"| {name} | {'yes' if ok else 'no'} | {', '.join(sorted(r['flagged'])) or 'none'} | {'; '.join(note)} | {r['seconds']:.0f}s |")

    done = [r for r in results if "error" not in r]
    secs = [r["seconds"] for r in done]
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    summary = [
        f"- Cases: {len(results)} ({len(done)} completed, {len(results) - len(done)} errors)",
        f"- Exact result (right card and exactly the expected problems): {exact}/{len(results)}",
        f"- Right rule card matched: {card_ok}/{len(done)}",
        f"- Planted problems caught (recall): {tp}/{tp + fn} = {recall:.0%}",
        f"- Flags that were real problems (precision): {tp}/{tp + fp} = {precision:.0%}",
        f"- Time per check: median {statistics.median(secs):.0f}s, max {max(secs):.0f}s" if secs else "- Time: n/a",
    ]
    intro = (["Every rule card, filled correctly and with its three demo mistakes, sent through the live `/api/check`.",
              "Each image is tested twice: a crisp render, and a simulated phone photo (3.5° tilt, blur, shrunk, JPEG quality 55).",
              "Expected problems come from applying the card's rules to a perfect read, so they are fixed in advance."]
             if args.set == "rendered" else
             ["Application letters converted to handwriting: English with an online text-to-handwriting tool",
              "(codeshack.io, three handwriting styles from neat to cursive), Bangla in the Galada handwriting-style font,",
              "all on lined paper. Expected problems are written in `eval/handwriting/expected.json` before the run."])
    report = [f"# FormBondhu evaluation: {args.set}", "", *intro, "",
              f"Run: {time.strftime('%Y-%m-%d %H:%M')} against {args.base}, engine: server default", "", "## Summary", "", *summary, "",
              "## Every case", "", "| Case | Exact | Flagged | Notes | Time |", "|---|---|---|---|---|", *rows, ""]
    name = "RESULTS" if args.set == "rendered" else "RESULTS_HANDWRITING"
    (EVAL / f"{name}{'_' + args.tag.upper() if args.tag else ''}.md").write_text("\n".join(report))
    print("\n".join(summary))
    print("\n".join(rows))


if __name__ == "__main__":
    main()
