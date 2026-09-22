"""Safe, framework-independent rendering of exact coded passages.

Offsets are Python Unicode character offsets, not bytes or browser UTF-16 units.
The renderer never guesses a passage or changes the underlying quotation.
"""

from __future__ import annotations

import colorsys
import hashlib
import html
from numbers import Integral
import re
from typing import Iterable, Mapping


def excerpt_digest(excerpt: str) -> str:
    return hashlib.sha256(excerpt.encode("utf-8")).hexdigest()


def exact_occurrences(excerpt: str, phrase: str) -> list[tuple[int, int]]:
    """Return every exact occurrence, including overlapping repeated phrases."""
    if not phrase or not phrase.strip():
        return []
    positions = []
    start = excerpt.find(phrase)
    while start != -1:
        positions.append((start, start + len(phrase)))
        start = excerpt.find(phrase, start + 1)
    return positions


def normalize_passages(excerpt: str, spans: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Validate and combine duplicate, overlapping or touching same-code spans."""
    checked = []
    for start, end in spans:
        if (
            isinstance(start, bool) or isinstance(end, bool)
            or not isinstance(start, Integral) or not isinstance(end, Integral)
            or not 0 <= start < end <= len(excerpt)
            or not excerpt[start:end].strip()
        ):
            raise ValueError("Each passage must select existing characters in the excerpt.")
        checked.append((int(start), int(end)))
    merged: list[tuple[int, int]] = []
    for start, end in sorted(checked):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def safe_code_color(value: object) -> str:
    color = str(value or "")
    return color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else "#0f62fe"


def _code_id(value: object) -> int | None:
    return int(value) if isinstance(value, Integral) and not isinstance(value, bool) else None


def code_display_colors(all_codes: Iterable[Mapping[str, object]]) -> dict[int, str]:
    """Return consistent, distinct shades for codes sharing a base colour.

    Call this with the complete codebook, including inactive codes, and reuse
    the mapping for every excerpt and its tags. Sorting by stable database ID
    makes shades independent of table order, code names and excerpt subsets.
    These are display colours only; the stored group colour is not changed.
    """
    groups: dict[str, set[int]] = {}
    for row in all_codes:
        code_id = _code_id(row.get("code_id", row.get("id")))
        if code_id is not None:
            color = safe_code_color(row.get("color")).lower()
            groups.setdefault(color, set()).add(code_id)

    colors: dict[int, str] = {}
    for base, ids in groups.items():
        ordered_ids = sorted(ids)
        colors[ordered_ids[0]] = base
        if len(ordered_ids) == 1:
            continue
        rgb = tuple(int(base[index:index + 2], 16) / 255 for index in (1, 3, 5))
        hue, base_lightness, saturation = colorsys.rgb_to_hls(*rgb)
        used_lightness = [base_lightness]
        used_colors = {base}
        # A bounded lightness range keeps underlines visible on the excerpt.
        # Spread early shades apart, then fill the widest remaining gaps.
        steps = max(100, len(ordered_ids) * 4)
        candidates: dict[str, float] = {}
        for index in range(steps + 1):
            lightness = 0.18 + 0.50 * index / steps
            shade_rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
            shade = "#" + "".join(f"{round(channel * 255):02x}" for channel in shade_rgb)
            if shade not in used_colors:
                candidates[shade] = lightness
        for code_id in ordered_ids[1:]:
            shade, lightness = max(
                candidates.items(),
                key=lambda item: (min(abs(item[1] - used) for used in used_lightness), item[1]),
            )
            colors[code_id] = shade
            used_colors.add(shade)
            used_lightness.append(lightness)
            del candidates[shade]
    return colors


def _validated_highlights(
    excerpt: str,
    spans: Iterable[Mapping[str, object]],
    reviews: Iterable[Mapping[str, object]] | None = None,
) -> tuple[dict[int, Mapping[str, object]], list[tuple[int, int, int]], dict[int, dict[str, object]]]:
    rows = list(spans)
    review_rows = list(reviews) if reviews is not None else rows
    codes: dict[int, Mapping[str, object]] = {}
    for row in review_rows:
        code_id = _code_id(row.get("code_id"))
        if code_id is not None:
            codes[code_id] = row
    digest = excerpt_digest(excerpt)
    valid: list[tuple[int, int, int]] = []
    problems: dict[int, str] = {}
    for row in rows:
        code_id = _code_id(row.get("code_id"))
        if code_id not in codes:
            continue
        if row.get("excerpt_sha256") != digest or (
            "excerpt" in row and row["excerpt"] != excerpt
        ):
            problems[code_id] = "Text changed - review the passage again"
            continue
        try:
            passage = normalize_passages(excerpt, [(row.get("start_offset"), row.get("end_offset"))])
        except (TypeError, ValueError):
            problems[code_id] = "Invalid passage - review needed"
            continue
        valid.append((*passage[0], code_id))

    states: dict[int, dict[str, object]] = {}
    valid_codes = {code_id for _, _, code_id in valid}
    for code_id in sorted(codes):
        row = codes[code_id]
        name = str(row.get("code_name") or f"Code {code_id}")
        status = str(row.get("status") or "unreviewed")
        if row.get("excerpt_sha256") not in (None, "", digest) or (
            "excerpt" in row and row["excerpt"] != excerpt
        ):
            problems[code_id] = "Text changed - review the passage again"
        state = problems.get(code_id) or {
            "reviewed": "Reviewed" if code_id in valid_codes else "No passage saved - review needed",
            "needs_review": "Needs review",
            "unreviewed": "Not reviewed yet",
        }.get(status, "Not reviewed yet")
        note = str(row.get("review_note") or "")
        tip = f"{name}: {state}" + (f". {note}" if note else "")
        states[code_id] = {
            "name": name,
            "state": state,
            "note": note,
            "status": "needs_review" if code_id in problems or (status == "reviewed" and code_id not in valid_codes) else status,
            "tooltip": tip,
            "needs_attention": state != "Reviewed",
        }
    # A stale review invalidates its passages even if an individual span has
    # a matching digest. Neither caller should display misleading evidence.
    valid = [passage for passage in valid if not problems.get(passage[2], "").startswith("Text changed")]
    return codes, valid, states


def highlight_review_states(
    excerpt: str,
    spans: Iterable[Mapping[str, object]],
    reviews: Iterable[Mapping[str, object]] | None = None,
) -> dict[int, dict[str, object]]:
    """Return plain-text review details for the existing code tags.

    The caller must HTML-escape strings if embedding them in HTML. Keeping
    these details separate avoids repeating the tag list above the excerpt.
    """
    return _validated_highlights(excerpt, spans, reviews)[2]


def render_highlighted_excerpt(
    excerpt: str,
    spans: Iterable[Mapping[str, object]],
    reviews: Iterable[Mapping[str, object]] | None = None,
    display_colors: Mapping[int, str] | None = None,
) -> str:
    """Render only the quote, showing all exact passages and overlap colours.

    Names and review details are available on hover or keyboard focus. Stale
    and invalid spans are not drawn, and missing passages are never guessed.
    Pass the same full-codebook display colours used by the code tags below.
    """
    codes, valid, states = _validated_highlights(excerpt, spans, reviews)

    boundaries = sorted({0, len(excerpt), *(start for start, _, _ in valid), *(end for _, end, _ in valid)})
    fragments = []
    for start, end in zip(boundaries, boundaries[1:]):
        text = html.escape(excerpt[start:end])
        active = sorted({code_id for a, b, code_id in valid if a <= start and end <= b})
        if not active:
            fragments.append(text)
            continue
        names = [str(codes[code_id].get("code_name") or f"Code {code_id}") for code_id in active]
        tooltip = "Highlighted for: " + "; ".join(names)
        details = [str(states[code_id]["tooltip"]) for code_id in active if states[code_id]["needs_attention"] or states[code_id]["note"]]
        if details:
            tooltip += ". " + "; ".join(details)
        colors = [safe_code_color((display_colors or {}).get(code_id, codes[code_id].get("color"))) for code_id in active]
        red, green, blue = (int(colors[0][i:i + 2], 16) for i in (1, 3, 5))
        images = ",".join(f"linear-gradient({color},{color})" for color in colors)
        positions = ",".join(f"0 calc(100% - {i * 3}px)" for i in range(len(colors)))
        styles = (
            f"background-color:rgba({red},{green},{blue},0.12);"
            f"background-image:{images};background-size:100% 2px;"
            f"background-position:{positions};background-repeat:no-repeat;"
            f"padding-bottom:{len(colors) * 3}px;"
        )
        fragments.append(
            f'<mark class="passage-highlight" data-code-ids="{",".join(map(str, active))}" '
            f'title="{html.escape(tooltip, quote=True)}" '
            f'aria-label="{html.escape(tooltip + ": " + excerpt[start:end], quote=True)}" '
            f'tabindex="0" style="{styles}">{text}</mark>'
        )
    return (
        '<div class="passage-view">'
        f'<div class="passage-text">{"".join(fragments)}</div>'
        '</div>'
    )
