#!/usr/bin/env python3
"""Styled Google Docs from light Markdown, in two passes.

  1) html : python gdoc_style.py html INPUT.md --theme editorial|academic [--accent #RRGGBB] --out DIR
            -> DIR/doc.html (upload with Drive create_file, contentMimeType text/html)
            -> DIR/manifest.json (paragraph roles, used by step 2)
  2) fix  : python gdoc_style.py fix READ_DOC.json --manifest DIR/manifest.json [--out requests.json]
            -> the full update_doc arguments {requests, writeControl}: A4 page, paragraph spacing,
               borders, alignment, and the CJK font on every Chinese run (Drive's HTML import drops
               CJK web fonts and paragraph borders, so this pass is required).

Markdown subset (blocks separated by blank lines):
  ::kicker TEXT | # Title | ::subtitle TEXT | ::meta TEXT | ::abstract LABEL | TEXT
  ## Heading | ### Subheading      (a leading number like "1", "1.1", "I." is colored with the accent)
  - item  /  1. item               (consecutive lines = one list)
  ::callout LABEL | TEXT           key point box
  > quote                          pull quote
  ::caption TEXT  then a | table | ::source TEXT
  ::footer TEXT
  inline: **bold**  *italic*
"""
import argparse, html, json, os, re, sys

CJK_RE = re.compile(r'[\u2E80-\u2FFF\u3001-\u303F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]')
NEUTRAL_RE = re.compile(r'[\s.,;:!?\'"\u201C\u201D\u2018\u2019()\[\]/&%+\-\u2013\u2014\u00B7\u2026\u3000]')

def rgb(hexs):
    h = hexs.lstrip("#")
    return {"red": round(int(h[0:2], 16) / 255, 3), "green": round(int(h[2:4], 16) / 255, 3), "blue": round(int(h[4:6], 16) / 255, 3)}

THEMES = {
  "editorial": dict(display="Playfair Display", body="Source Serif 4", cjk="Noto Serif SC",
                    ink="#1C1B19", muted="#5C5852", rule="#D9D5CE", accent="#8C2F25", grid="#E6E2DB",
                    body_pt=11, line=160),
  "academic":  dict(display="EB Garamond", body="EB Garamond", cjk="Noto Serif SC",
                    ink="#1A1A1A", muted="#4A4A4A", rule="#1A1A1A", accent="#1F3A5F", grid=None,
                    body_pt=12, line=150),
}

# ---------------------------------------------------------------- pass 1: html

def spans(text, latin, cjk):
    out, cur, buf, pend = [], None, "", ""
    for ch in text:
        if NEUTRAL_RE.match(ch) or ch.isdigit():
            if cur is None: pend += ch
            else: buf += ch
            continue
        s = "c" if CJK_RE.match(ch) else "l"
        if cur is None: cur, buf, pend = s, pend + ch, ""
        elif s == cur: buf += ch
        else: out.append((cur, buf)); cur, buf = s, ch
    out.append((cur or "l", buf or pend))
    return "".join(f'<span style="font-family:\'{cjk if s == "c" else latin}\'">{html.escape(t)}</span>' for s, t in out if t)

def inline(text, latin, cjk):
    res = []
    for p in re.split(r'(\*\*[^*]+\*\*|\*[^*]+\*)', text):
        if p.startswith("**") and p.endswith("**") and len(p) > 4: res.append(f"<b>{spans(p[2:-2], latin, cjk)}</b>")
        elif p.startswith("*") and p.endswith("*") and len(p) > 2: res.append(f"<i>{spans(p[1:-1], latin, cjk)}</i>")
        elif p: res.append(spans(p, latin, cjk))
    return "".join(res)

def plain(text):
    return re.sub(r'\*\*([^*]+)\*\*|\*([^*]+)\*', lambda m: m.group(1) or m.group(2), text)

def build_html(md, theme, accent):
    T = dict(THEMES[theme]); T["accent"] = accent or T["accent"]
    ed = theme == "editorial"
    A, ink, muted = T["accent"], T["ink"], T["muted"]
    LD, LB, CJ, bp = T["display"], T["body"], T["cjk"], T["body_pt"]
    D = lambda t: inline(t, LD, CJ)
    B = lambda t: inline(t, LB, CJ)
    out, roles, caption = [], [], None

    def para(role, text_plain, inner, css=""):
        roles.append({"role": role, "text": text_plain})
        out.append(f'<p style="margin:0;color:{ink};{css}">{inner}</p>')

    def heading(tag, role, t, size):
        m = re.match(r'^((?:[IVX]+\.|\d+(?:\.\d+)*\.?))\s+(.*)$', t)
        inner = (f'<span style="color:{A}">{spans(m.group(1), LD, CJ)}</span>{spans(chr(0x3000), LD, CJ)}{D(m.group(2))}'
                 if m else D(t))
        txt = (m.group(1) + "\u3000" + plain(m.group(2))) if m else plain(t)
        roles.append({"role": role, "text": txt})
        out.append(f'<{tag} style="font-size:{size}pt;font-weight:bold;color:{ink}">{inner}</{tag}>')

    for b in re.split(r'\n\s*\n', md.strip()):
        lines = [l.rstrip() for l in b.strip().split("\n")]
        f = lines[0]
        if f.startswith("::kicker "):
            t = f[9:].strip()
            t = t.upper() if ed else t
            para("kicker", t, spans(t, LB, CJ), f"font-size:{8 if ed else 10}pt;{'font-weight:bold;' if ed else ''}color:{A if ed else muted}")
        elif f.startswith("# "):
            para("title", plain(f[2:]), D(f[2:]), f"font-size:{30 if ed else 24}pt;{'font-weight:bold;' if ed else ''}")
        elif f.startswith("::subtitle "):
            t = f[11:].strip(); para("subtitle", plain(t), D(t), f"font-size:{14 if ed else 13}pt;font-style:italic;color:{'#4A4742' if ed else ink}")
        elif f.startswith("::meta "):
            t = f[7:].strip(); para("meta", plain(t), B(t), f"font-size:{9 if ed else 11}pt;color:{muted}")
        elif f.startswith("::abstract "):
            label, _, rest = f[11:].partition("|")
            para("abstract", plain(label.strip()) + "\u3000" + plain(rest.strip()),
                 f'<b>{B(label.strip())}</b>{spans(chr(0x3000), LB, CJ)}{B(rest.strip())}', f"font-size:{bp-1}pt")
        elif f.startswith("### "):
            heading("h3", "h3", f[4:].strip(), 13 if ed else 12.5)
        elif f.startswith("## "):
            heading("h2", "h2", f[3:].strip(), 18 if ed else 15)
        elif re.match(r'^(-|\d+\.)\s', f):
            ordered = f[0].isdigit(); tag = "ol" if ordered else "ul"
            lis = []
            for l in lines:
                t = re.sub(r'^(-|\d+\.)\s+', "", l)
                roles.append({"role": "li", "text": plain(t)})
                lis.append(f'<li style="font-size:{bp}pt;color:{ink}"><p style="margin:0">{B(t)}</p></li>')
            lt = ("lower-roman" if not ed else "decimal") if ordered else "disc"
            out.append(f'<{tag} style="list-style-type:{lt}">{"".join(lis)}</{tag}>')
        elif f.startswith("::callout "):
            label, _, text = f[10:].partition("|")
            label, text = label.strip(), text.strip()
            if ed:
                para("callout_label", label.upper(), spans(label.upper(), LB, CJ), f"font-size:8pt;font-weight:bold;color:{A}")
                para("callout_text", plain(text), D(text), "font-size:14pt")
            else:
                para("callout_box", plain(label) + "\u3000" + plain(text),
                     f'<b>{B(label)}</b>{spans(chr(0x3000), LB, CJ)}<i>{B(text)}</i>', f"font-size:{bp}pt")
        elif f.startswith(">"):
            t = " ".join(l.lstrip("> ").strip() for l in lines)
            para("quote", plain(t), D(t) if ed else B(t), f"font-size:{16 if ed else bp}pt;font-style:italic")
        elif f.startswith("::caption "):
            caption = f[10:].strip()
        elif f.startswith("::source "):
            t = f[9:].strip(); para("source", plain(t), B(t), f"font-size:9pt;color:{muted};{'font-style:italic' if ed else ''}")
        elif f.startswith("::footer "):
            t = f[9:].strip(); para("footer", plain(t), B(t), f"font-size:9pt;color:{muted}")
        elif f.startswith("|"):
            if caption:
                para("caption", plain(caption), B(caption), f"font-size:{10 if ed else 11}pt;{'font-weight:bold' if ed else ''}")
                caption = None
            rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines if not re.match(r'^\|\s*:?-', l)]
            n = len(rows)
            thick, thin = f"{1 if ed else 1.5}pt solid {ink}", f"0.75pt solid {ink}"
            light = f"0.75pt solid {T['grid']}" if T["grid"] else "none"
            numcol = [all(re.match(r'^[\d.,%+\-–]+$', rr[c]) for rr in rows[1:] if c < len(rr)) for c in range(len(rows[0]))]
            trs = []
            for r, row in enumerate(rows):
                tds = []
                for ci, cell in enumerate(row):
                    num = ci < len(numcol) and numcol[ci]
                    bt = thick if r == 0 else "none"
                    bb = thin if r == 0 else (thick if r == n - 1 else light)
                    inner = B(cell)
                    if r == 0: inner = f"<b>{inner}</b>"
                    tds.append(f'<td style="border-top:{bt};border-bottom:{bb};border-left:none;border-right:none;padding:4pt 6pt;vertical-align:top">'
                               f'<p style="margin:0;font-size:{bp-1}pt;{"text-align:right;" if num else ""}color:{ink}">{inner}</p></td>')
                trs.append("<tr>" + "".join(tds) + "</tr>")
            out.append(f'<table style="border-collapse:collapse;width:100%">{"".join(trs)}</table>')
        else:
            t = " ".join(lines); para("body", plain(t), B(t), f"font-size:{bp}pt")
    doc = f'<html><head><meta charset="utf-8"></head><body style="font-family:\'{LB}\'">' + "\n".join(out) + "</body></html>"
    return doc, {"theme": theme, "accent": T["accent"], "paragraphs": roles}

# ---------------------------------------------------------------- pass 2: fix

def border(width, color, pad):
    return {"width": {"magnitude": width, "unit": "PT"}, "padding": {"magnitude": pad, "unit": "PT"},
            "dashStyle": "SOLID", "color": {"color": {"rgbColor": rgb(color)}}}

def role_styles(theme, accent):
    T = THEMES[theme]; ink, rule = T["ink"], T["rule"]; L = T["line"]
    pt = lambda v: {"magnitude": v, "unit": "PT"}
    if theme == "editorial":
        return {
          "kicker":        dict(spaceAbove=pt(0), spaceBelow=pt(16), borderBottom=border(0.75, ink, 5)),
          "title":         dict(named="TITLE", lineSpacing=110, spaceAbove=pt(0), spaceBelow=pt(4)),
          "subtitle":      dict(spaceAbove=pt(0), spaceBelow=pt(14)),
          "meta":          dict(spaceAbove=pt(0), spaceBelow=pt(24), borderTop=border(0.75, rule, 4), borderBottom=border(0.75, rule, 4)),
          "h2":            dict(lineSpacing=120, spaceAbove=pt(24), spaceBelow=pt(8), keepWithNext=True),
          "h3":            dict(lineSpacing=120, spaceAbove=pt(16), spaceBelow=pt(6), keepWithNext=True),
          "body":          dict(lineSpacing=L, spaceAbove=pt(0), spaceBelow=pt(8)),
          "li":            dict(lineSpacing=L, spaceAbove=pt(0), spaceBelow=pt(3)),
          "callout_label": dict(spaceAbove=pt(14), spaceBelow=pt(2), borderTop=border(1.5, accent, 8), keepWithNext=True),
          "callout_text":  dict(lineSpacing=140, spaceAbove=pt(0), spaceBelow=pt(16), borderBottom=border(0.75, accent, 8)),
          "quote":         dict(alignment="CENTER", lineSpacing=140, spaceAbove=pt(18), spaceBelow=pt(18), indentStart=pt(40), indentFirstLine=pt(40), indentEnd=pt(40)),
          "caption":       dict(spaceAbove=pt(6), spaceBelow=pt(4), keepWithNext=True),
          "source":        dict(spaceAbove=pt(4), spaceBelow=pt(14)),
          "footer":        dict(spaceAbove=pt(24), borderTop=border(0.75, rule, 5)),
        }
    return {
      "kicker":     dict(alignment="CENTER", spaceBelow=pt(8)),
      "title":      dict(named="TITLE", alignment="CENTER", lineSpacing=115, spaceAbove=pt(0), spaceBelow=pt(4)),
      "subtitle":   dict(alignment="CENTER", spaceAbove=pt(0), spaceBelow=pt(10)),
      "meta":       dict(alignment="CENTER", spaceAbove=pt(0), spaceBelow=pt(18)),
      "abstract":   dict(alignment="JUSTIFIED", lineSpacing=140, spaceAbove=pt(0), spaceBelow=pt(18), indentStart=pt(30), indentFirstLine=pt(30), indentEnd=pt(30)),
      "h2":         dict(lineSpacing=120, spaceAbove=pt(20), spaceBelow=pt(6), keepWithNext=True),
      "h3":         dict(lineSpacing=120, spaceAbove=pt(14), spaceBelow=pt(6), keepWithNext=True),
      "body":       dict(alignment="JUSTIFIED", lineSpacing=L, spaceAbove=pt(0), spaceBelow=pt(6), indentFirstLine=pt(24), indentStart=pt(0)),
      "li":         dict(lineSpacing=L, spaceAbove=pt(0), spaceBelow=pt(2)),
      "callout_box": dict(lineSpacing=L, spaceAbove=pt(10), spaceBelow=pt(14), indentStart=pt(8), indentFirstLine=pt(8), indentEnd=pt(8),
                          borderTop=border(0.75, ink, 8), borderBottom=border(0.75, ink, 8), borderLeft=border(0.75, ink, 10), borderRight=border(0.75, ink, 10)),
      "quote":      dict(lineSpacing=L, spaceAbove=pt(10), spaceBelow=pt(10), indentStart=pt(36), indentFirstLine=pt(36), indentEnd=pt(36)),
      "caption":    dict(alignment="CENTER", spaceAbove=pt(8), spaceBelow=pt(4), keepWithNext=True),
      "source":     dict(alignment="CENTER", spaceAbove=pt(4), spaceBelow=pt(14)),
      "footer":     dict(spaceAbove=pt(24), borderTop=border(0.5, "#999999", 5)),
    }

def utf16len(s): return len(s.encode("utf-16-le")) // 2

def classify(text):
    cls = ["c" if CJK_RE.match(ch) else ("n" if NEUTRAL_RE.match(ch) else "l") for ch in text]
    i = 0
    while i < len(cls):  # neutral runs: CJK when touching CJK and not touching Latin
        if cls[i] != "n": i += 1; continue
        j = i
        while j < len(cls) and cls[j] == "n": j += 1
        left = cls[i - 1] if i > 0 else None; right = cls[j] if j < len(cls) else None
        fill = "c" if (left == "c" or right == "c") and "l" not in (left, right) else "l"
        if left == "c" and right == "c": fill = "c"
        if fill == "c" and all(text[k].isspace() and text[k] != "\u3000" for k in range(i, j)) and (left == "l" or right == "l"): fill = "l"
        for k in range(i, j): cls[k] = fill
        i = j
    return cls

def walk(content, tab_id, out_paras, out_runs, in_table=False):
    for el in content:
        if "paragraph" in el:
            p = el["paragraph"]
            if not in_table:
                txt = "".join(e.get("textRun", {}).get("content", "") for e in p["elements"]).rstrip("\n")
                out_paras.append((el["startIndex"], el["endIndex"], txt))
            for e in p["elements"]:
                if "textRun" in e: out_runs.append((e["startIndex"], e["textRun"]))
        elif "table" in el:
            for row in el["table"]["tableRows"]:
                for cell in row["tableCells"]:
                    walk(cell["content"], tab_id, out_paras, out_runs, True)

def build_fix(docjson, manifest):
    d = docjson.get("content", docjson)
    tab = d["tabs"][0]; tab_id = tab["tabProperties"]["tabId"]; body = tab["documentTab"]["body"]["content"]
    theme = manifest["theme"]; T = THEMES[theme]; styles = role_styles(theme, manifest["accent"])
    paras, runs = [], []
    walk(body, tab_id, paras, runs)
    reqs = [{"updateDocumentStyle": {"tabId": tab_id, "documentStyle": {
              "pageSize": {"width": {"magnitude": 595.28, "unit": "PT"}, "height": {"magnitude": 841.89, "unit": "PT"}},
              "marginTop": {"magnitude": 60, "unit": "PT"}, "marginBottom": {"magnitude": 56, "unit": "PT"},
              "marginLeft": {"magnitude": 66, "unit": "PT"}, "marginRight": {"magnitude": 66, "unit": "PT"}},
              "fields": "pageSize,marginTop,marginBottom,marginLeft,marginRight"}}]
    # match manifest paragraphs to document paragraphs in order (skip empty doc paragraphs)
    norm = lambda s: re.sub(r'\s+', '', s)
    want = manifest["paragraphs"]; wi = 0; unmatched = []
    for (s, e, txt) in paras:
        if wi >= len(want): break
        if not txt.strip(): continue
        if norm(txt) != norm(want[wi]["text"]):
            unmatched.append((txt[:40], want[wi]["text"][:40])); continue
        st = dict(styles.get(want[wi]["role"], {})); wi += 1
        named = st.pop("named", None)
        rng = {"startIndex": s, "endIndex": e, "tabId": tab_id}
        if named:
            reqs.append({"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": named}, "fields": "namedStyleType"}})
        if st:
            reqs.append({"updateParagraphStyle": {"range": rng, "paragraphStyle": st, "fields": ",".join(st.keys())}})
    # fonts: CJK runs -> cjk font; Latin runs left in a fallback font -> body font
    ok_latin = {T["display"], T["body"]}
    for start, tr in runs:
        text = tr["content"]; fam = tr.get("textStyle", {}).get("weightedFontFamily", {}).get("fontFamily")
        cls = classify(text); pos = start; i = 0
        while i < len(text):
            j = i
            while j < len(text) and cls[j] == cls[i]: j += 1
            seg = text[i:j]; ln = utf16len(seg)
            seg_clean = seg.rstrip("\n")
            if seg_clean:
                target = T["cjk"] if cls[i] == "c" else (fam if fam in ok_latin else T["body"])
                bold = tr.get("textStyle", {}).get("bold", False)
                italic = tr.get("textStyle", {}).get("italic", False)
                cj = target == T["cjk"]
                if target != fam or (bold and cj) or (italic and cj):
                    ts = {"weightedFontFamily": {"fontFamily": target, "weight": 700 if bold else 400}}
                    fields = "weightedFontFamily"
                    if italic and cj:  # Chinese has no true italic: drop the fake slant
                        ts["italic"] = False; fields += ",italic"
                    reqs.append({"updateTextStyle": {"range": {"startIndex": pos, "endIndex": pos + utf16len(seg_clean), "tabId": tab_id},
                                 "textStyle": ts, "fields": fields}})
            pos += ln; i = j
    # merge touching font ranges with the same family
    merged = []
    for r in reqs:
        u = r.get("updateTextStyle")
        if u and merged and "updateTextStyle" in merged[-1]:
            p = merged[-1]["updateTextStyle"]
            if p["range"]["endIndex"] == u["range"]["startIndex"] and p["textStyle"] == u["textStyle"]:
                p["range"]["endIndex"] = u["range"]["endIndex"]; continue
        merged.append(r)
    reqs = merged
    return {"requests": reqs, "writeControl": {"requiredRevisionId": d["revisionId"]}}, unmatched, wi, len(want)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("html"); h.add_argument("input"); h.add_argument("--theme", default="editorial", choices=THEMES)
    h.add_argument("--accent"); h.add_argument("--out", required=True)
    f = sub.add_parser("fix"); f.add_argument("docjson"); f.add_argument("--manifest", required=True); f.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "html":
        os.makedirs(a.out, exist_ok=True)
        doc, man = build_html(open(a.input, encoding="utf-8").read(), a.theme, a.accent)
        open(os.path.join(a.out, "doc.html"), "w", encoding="utf-8").write(doc)
        json.dump(man, open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"wrote {a.out}/doc.html ({len(doc)} chars) and manifest.json ({len(man['paragraphs'])} paragraphs)")
    else:
        res, unmatched, got, total = build_fix(json.load(open(a.docjson, encoding="utf-8")), json.load(open(a.manifest, encoding="utf-8")))
        s = json.dumps(res, ensure_ascii=False)
        if a.out: open(a.out, "w", encoding="utf-8").write(s)
        else: print(s)
        print(f"matched {got}/{total} paragraphs, {len(res['requests'])} requests", file=sys.stderr)
        for u in unmatched: print("  skipped doc paragraph:", u, file=sys.stderr)
