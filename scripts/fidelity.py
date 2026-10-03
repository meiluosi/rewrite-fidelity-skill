#!/usr/bin/env python3
"""Check that a rewrite kept the meaning-bearing parts of the original.

Style linters (ste-lint.py, zh-lint.py) check the shape of ONE text. This
script compares TWO texts: an original and its rewrite. It extracts the parts
that carry meaning and that a simplifying rewrite tends to lose or change:

    literals     code spans, code blocks, URLs, paths, flags, identifiers,
                 error codes, versions          -> must survive verbatim
    numbers      Arabic, Chinese and English number words, normalized
                 ("三" == "3" == "three")       -> same multiset
    modality     requirement / prohibition / recommendation / permission /
                 ability / possibility / approximation, per language
    conditions   if / unless / until / 如果 / 除非 / 否则 / 仅当 ...
    negation     not / never / 不 / 没有 / 未 ...
    scope        all / only / at least / 所有 / 仅 / 至少 ...
    quoted       "..." “...” 「...」 (UI labels, error text)

It reports what disappeared or appeared. It cannot prove that meaning is
preserved: a count that matches can still hide a flipped condition. Use it as
the mechanical first pass, then do the claim-by-claim check in SKILL.md.

Usage:
    fidelity.py ORIGINAL REWRITE            # files; "-" reads stdin
    fidelity.py --json ORIGINAL REWRITE
    fidelity.py --strict ORIGINAL REWRITE   # warnings also fail the run
    fidelity.py --selftest

Exit 0 when no error-level finding, 1 otherwise, 2 on usage error.
Stdlib only, Python 3.8+.
"""
import argparse
import json
import re
import sys
from collections import Counter

# ---------------------------------------------------------------------------
# Literal extraction. Each literal is removed from the text after extraction
# so that later passes (numbers, modals) do not count it a second time.
# ---------------------------------------------------------------------------

FENCE_BLOCK = re.compile(r"^[ \t]*(```|~~~)[^\n]*\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
URL = re.compile(r"\bhttps?://[^\s)\]>\"'，。、；）」]+")
PATH = re.compile(
    r"(?<![\w/])(?:~|\.{1,2})?/(?:[\w.\-]+/)*[\w.\-]*[\w\-]"     # /etc/x, ./a/b, ~/x
    r"|(?<![\w/.])[\w\-]+(?:/[\w.\-]*[\w\-])+"                     # src/app/main.py
)
FILENAME = re.compile(
    r"(?<![\w.])[\w\-]+\.(?:py|js|mjs|ts|tsx|jsx|json|ya?ml|md|toml|sh|go|rs|java|"
    r"kt|rb|php|c|h|cpp|txt|log|csv|conf|ini|env|lock|sql|html|css|xml)\b"
)
FLAG = re.compile(r"(?<![\w\-])--?[A-Za-z][\w\-]*(?:=\S+)?")
ERROR_CODE = re.compile(r"\b(?:[A-Z]{1,6}-?\d{2,}|0x[0-9A-Fa-f]{2,})\b")
VERSION = re.compile(r"\bv?\d+(?:\.\d+){2,}(?:[-+][\w.]+)?\b")
CONST = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b")              # ENV_VAR, MAX_RETRY
SNAKE = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")
CAMEL = re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b")
CALL = re.compile(r"\b[A-Za-z_][\w.]*\(\)")
QUOTED = re.compile(r"\"([^\"\n]{1,80})\"|“([^”\n]{1,80})”|「([^」\n]{1,80})」|『([^』\n]{1,80})』")

# (kind, pattern, severity-if-missing). Order matters: wider patterns first.
LITERAL_KINDS = [
    ("code-block", FENCE_BLOCK, "error"),
    ("inline-code", INLINE_CODE, "error"),
    ("url", URL, "error"),
    ("version", VERSION, "error"),
    ("path", PATH, "error"),
    ("filename", FILENAME, "error"),
    ("flag", FLAG, "error"),
    ("call", CALL, "error"),
    ("error-code", ERROR_CODE, "error"),
    ("constant", CONST, "error"),
    ("identifier", SNAKE, "error"),
    ("identifier", CAMEL, "error"),
    ("quoted", QUOTED, "warn"),
]


def _norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def extract_literals(text):
    """Return (Counter of (kind, literal), text with literals blanked out)."""
    found = Counter()
    for kind, pattern, _sev in LITERAL_KINDS:
        def take(m, kind=kind):
            if kind == "code-block":
                value = _norm_ws(m.group(2))
            elif kind == "inline-code":
                value = m.group(1).strip()
            elif kind == "quoted":
                value = next(g for g in m.groups() if g is not None).strip()
            else:
                value = m.group(0)
            if kind == "quoted":
                # Quoted prose stays in the text: its words still carry modals,
                # numbers and negation that later passes must count.
                found[(kind, value)] += 1
                return m.group(0)
            if value:
                found[(kind, value)] += 1
            return " ⟨…⟩ "  # visible placeholder; no later pass matches it
        text = pattern.sub(take, text)
    return found, text


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
CN_BIG = {"万": 10_000, "亿": 100_000_000}


def cn2num(s):
    """Convert a Chinese numeral string (一百二十三, 两千, 十五, 三万) to int."""
    total, section, number = 0, 0, 0
    for ch in s:
        if ch in CN_DIGITS:
            number = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            section += (number or 1) * CN_UNITS[ch]
            number = 0
        elif ch in CN_BIG:
            total += (section + number) * CN_BIG[ch]
            section, number = 0, 0
        else:
            return None
    return total + section + number


# Measure words after which a Chinese numeral is a real quantity.
CN_QTY_UNIT = (r"(?:毫秒|秒钟?|分钟|小时|天|日|周|星期|个月|月|年|次|倍|遍|轮|位|台|条|项|"
               r"行|列|字节?|个字符|字符|层|级|步|种|个|份|张|页|块|核|线程|进程|副本|实例|节点|"
               r"MB|GB|KB|TB|ms|s|%|％)")
# A bare 一/两 is often an article ("一个文件"), so it only counts before
# measure words that make it a quantity.
CN_SINGLE_UNIT = r"(?:毫秒|秒钟?|分钟|小时|天|日|周|星期|个月|月|年|次|倍|遍|轮|副本|实例|节点|MB|GB|KB|TB|%|％)"
CN_NUM = re.compile(
    r"(?<![第周星期礼拜初])(?P<n>[零〇一二两三四五六七八九十百千万亿]{2,}|[三四五六七八九十])(?=\s*" + CN_QTY_UNIT + ")"
    r"|(?<![第周星期礼拜初统唯])(?P<n1>[一两])(?=\s*" + CN_SINGLE_UNIT + ")"
)
CN_PERCENT = re.compile(r"百分之(?P<n>[零〇一二两三四五六七八九十百千]+|\d+(?:\.\d+)?)")

EN_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
    "twice": 2, "thrice": 3,
}
EN_NUM = re.compile(r"\b(" + "|".join(EN_WORDS) + r")\b", re.I)
EN_ONE = re.compile(
    r"\b(one|once)\b(?=\s+(?:second|minute|hour|day|week|month|year|time|retry|"
    r"attempt|byte|request|more|per)|(?:\s*[.,;]|\s*$))", re.I)
EN_ONE_LOOSE = re.compile(r"\bonce\b", re.I)

LIST_MARKER = re.compile(r"^[ \t]*(?:\d+[.)]|[-*+])[ \t]+", re.M)
ORDINAL = re.compile(r"(?:第\s*\d+\s*[步条项章节个次]?|\b[Ss]tep\s+\d+\b|\b\d+(?:st|nd|rd|th)\b)")
ARABIC = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w])|(?<![\w.])\d+(?:\.\d+)?")


def _fmt_num(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def extract_numbers(text):
    """Return Counter of normalized numeric values plus a value->snippet map."""
    text = LIST_MARKER.sub(" ", text)
    text = ORDINAL.sub(" ", text)
    found, where = Counter(), {}

    def add(value, m, src):
        key = _fmt_num(value)
        found[key] += 1
        where.setdefault(key, _context(src, m.start(), m.end()))

    def sub_percent(m):
        raw = m.group("n")
        val = float(raw) if raw[0].isdigit() else cn2num(raw)
        if val is not None:
            add(val, m, text)
        return " \u2063 "
    work = CN_PERCENT.sub(sub_percent, text)

    def sub_cn(m):
        raw = m.group("n") or m.group("n1")
        val = cn2num(raw)
        if val is not None:
            add(val, m, work)
        return " \u2063 "
    work = CN_NUM.sub(sub_cn, work)

    def sub_en(m):
        add(EN_WORDS[m.group(1).lower()], m, work)
        return " "
    work = EN_NUM.sub(sub_en, work)

    def sub_one(m):
        add(1, m, work)
        return " "
    work = EN_ONE.sub(sub_one, work)

    for m in ARABIC.finditer(work):
        add(float(m.group(0).replace(",", "")), m, work)
    return found, where


# ---------------------------------------------------------------------------
# Lexical categories: modality, conditions, negation, scope.
# Patterns are matched longest-first and blanked as they match, so that
# "must not" is not also counted as "must", and 不建议 not also as 建议.
# ---------------------------------------------------------------------------

CJK = r"一-鿿"

CATEGORIES = [
    # --- modality -----------------------------------------------------------
    ("modal.not-recommend", "error", [
        r"\bshould\s+not\b", r"\bshouldn't\b", r"\bnot\s+recommended\b",
        r"不建议", r"不推荐", r"不宜", r"最好不要", r"最好别", r"尽量不要", r"尽量别", r"尽量避免",
    ]),
    ("modal.prohibit", "error", [
        r"(?:^|(?<=[.!?:]\s)|(?<=\n))(?:Do\s+not|Don't|Never)\b",
        r"(?<![得])不要(?![求紧])", r"千万别", r"(?<![区类级特分识个告])别(?=[再把在用去让做动删改碰])",
        r"\b(?:must|shall)\s+not\b", r"\b(?:mustn't|shan't)\b", r"\bis\s+not\s+allowed\b",
        r"\bmay\s+not\b", r"\bis\s+(?:forbidden|prohibited)\b",
        r"不得", r"禁止", r"严禁", r"不准", r"不允许", r"不可以", r"切勿", r"请勿", r"不应该?", r"不应当",
        r"不能够?", r"无法", r"不可(?!能|用|读|见|靠|逆)",
    ]),
    ("modal.not-required", "error", [
        r"\b(?:need|needs)\s+not\b", r"\bdo(?:es)?\s+not\s+(?:need|have)\s+to\b",
        r"\bnot\s+required\b", r"不必", r"无需", r"无须", r"不需要", r"不用",
    ]),
    ("modal.possibility", "error", [
        r"\b(?:may|might|could|must)\s+have\b", r"\bmight\b", r"\bcould\b",
        r"\b(?:possibly|probably|likely|unlikely|perhaps|maybe)\b",
        r"\b(?:appears?|seems?)\s+to\b",
        r"不可能", r"可能", r"也许", r"或许", r"大概", r"似乎", r"恐怕", r"估计", r"未必", r"不一定",
    ]),
    ("modal.approx", "error", [
        r"\b(?:about|approximately|around|roughly|nearly|almost)\b(?=\s*[~\d])",
        r"~\s*(?=\d)", r"大约", r"大概(?=\s*\d)", r"约(?=\s*[\d一二两三四五六七八九十百千])",
        r"左右", r"上下(?=[，。,.\s]|$)", r"近(?=\s*\d)",
    ]),
    ("modal.require", "error", [
        r"\bmust\b", r"\bshall\b", r"\b(?:is|are)\s+required\s+to\b", r"\bhave\s+to\b",
        r"\bhas\s+to\b", r"\bneeds?\s+to\b",
        r"必须", r"务必", r"必需", r"须(?!知)", r"应当", r"应该", r"需要(?=[" + CJK + r"])",
        r"(?<![响对适相反供回效答呼感照理])应(?![用答对该当急变付聘届征邀试])",
    ]),
    ("modal.recommend", "warn", [
        r"\bshould\b", r"\b(?:is\s+)?recommended\b", r"\bought\s+to\b",
        r"建议", r"推荐", r"最好", r"尽量", r"(?<![便适合])宜(?![昌宾家人])",
    ]),
    ("modal.may", "warn", [r"\bmay\b"]),               # permission or possibility: ambiguous in English
    ("modal.permit", "warn", [
        r"\b(?:is|are)\s+allowed\s+to\b", r"\bcan\b", r"\boptional(?:ly)?\b",
        r"可以", r"允许", r"可选", r"(?<![不])可(?=[以选])",
    ]),
    ("modal.ability", "warn", [
        r"能够", r"(?<![可功性智技职本潜效体动热电节核才万只未])能(?![力量源耗效手])",
    ]),
    # --- conditions and exceptions ------------------------------------------
    ("condition", "error", [
        r"\bonly\s+if\b", r"\bif\b", r"\bunless\b", r"\bwhen(?:ever)?\b", r"\buntil\b",
        r"\botherwise\b", r"\bexcept\b", r"\bprovided\s+that\b", r"\bin\s+case\b",
        r"\bbefore\b", r"\bafter\b", r"\bwhile\b",
        r"仅当", r"只有当?", r"如果", r"假如", r"假设", r"若(?!干)", r"一旦", r"只要", r"除非", r"否则",
        r"除了", r"(?<=[" + CJK + r"])(?:以外|之外)", r"直到", r"前提是", r"条件是",
        r"之前", r"之后", r"以前", r"以后",
        # 「当 X 时，」和「X 时，」都计一次，所以只数「时，」，不数「当」。
        r"(?<=[" + CJK + r"\w%％)）])\s*时(?=[，,])",
    ]),
    # --- negation (counted after the modal negations above are consumed) ----
    ("negation", "warn", [
        r"\bnot\b", r"\bn't\b", r"\bnever\b", r"\bno\b", r"\bnone\b", r"\bnothing\b",
        r"\bneither\b", r"\bnor\b", r"\bwithout\b", r"\bcannot\b",
        r"没有", r"没(?![收])", r"未能", r"未(?!来|知)", r"(?<![并])非(?!常|法|凡)", r"别(?=[" + CJK + r"])(?<!区别)(?<!类别)(?<!级别)(?<!特别)(?<!分别)(?<!识别)(?<!个别)(?<!告别)",
        r"勿", r"无(?!论)",
        r"不(?!同|仅|断|久|过|少|错|管|论|如|然|止|但|光|只|外乎)",
    ]),
    # --- scope and quantifiers ----------------------------------------------
    ("scope.limit", "error", [
        r"\bat\s+(?:least|most)\b", r"\bno\s+(?:more|less|fewer)\s+than\b", r"\bup\s+to\b(?=\s*\d)",
        r"\b(?:more|less|fewer)\s+than\b", r"\bonly\b",
        r"至少", r"至多", r"最多", r"最少", r"不超过", r"不少于", r"不低于", r"不高于",
        r"(?<=[\d％%个次天秒时岁元位人台倍行项条BbKkMmGgTt])\s*(?:以上|以下|以内|之内)", r"超过", r"不满", r"不足", r"低于", r"高于",
        r"仅", r"(?<![不])只(?!要|有当)", r"[≥≤<>]=?",
    ]),
    ("scope", "warn", [
        r"\b(?:all|every|each|any|always|some|both|either)\b",
        r"所有", r"全部", r"每(?=[个次一条项位])", r"任何", r"任一", r"总是", r"始终", r"从不", r"永远",
        r"部分", r"某些", r"一些",
    ]),
]

GROWTH_IS_ERROR = {"modal.require", "modal.prohibit"}

_COMPILED = [
    (name, sev, re.compile("|".join(f"(?:{p})" for p in pats), re.I))
    for name, sev, pats in CATEGORIES
]


def extract_categories(text):
    """Return {category: (count, [snippets])}."""
    out = {}
    work = text
    for name, _sev, pattern in _COMPILED:
        hits = []

        def take(m):
            hits.append(_context(text, m.start(), m.end()))  # offsets match: blanks keep length
            return "\u2063" * len(m.group(0))  # keep offsets stable for context
        work = pattern.sub(take, work)
        out[name] = (len(hits), hits)
    return out


def _context(text, start, end, width=14):
    left = text[max(0, start - width):start]
    right = text[end:end + width]
    snippet = (left + "[" + text[start:end] + "]" + right)
    snippet = snippet.replace("\u2063", "").replace("\n", " ")
    return re.sub(r"\s+", " ", snippet).strip()


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

MESSAGES = {
    "modal.prohibit": "Prohibition count changed. A lost 'must not'/'不得' turns a ban into silence.",
    "modal.not-recommend": "'should not'/'不建议' count changed.",
    "modal.not-required": "'need not'/'不必' count changed.",
    "modal.possibility": "Hedge count changed. A dropped 'may have'/'可能' promotes a guess to a fact.",
    "modal.approx": "Approximation marker changed. '约 5 秒' -> '5 秒' claims precision the source did not have.",
    "modal.require": "Requirement count changed. Check for MUST<->SHOULD drift (必须/应 vs 建议).",
    "modal.recommend": "Recommendation count changed. Check it was not promoted to a requirement or dropped.",
    "modal.may": "'may' count changed. English 'may' is permission OR possibility. Check which one moved.",
    "modal.permit": "Permission count changed.",
    "modal.ability": "Ability (能/无法) count changed.",
    "condition": "Condition/exception/sequence markers changed. A dropped 'unless'/'除非' widens the instruction.",
    "negation": "Negation count changed. Re-read every negated clause: polarity flips are the costliest error.",
    "scope.limit": "Bound or limit changed (at most/only/至少/不超过/以上). A lost bound turns a limit into an exact value or removes it.",
    "scope": "Quantifier changed (all/every/some/所有/每个/部分).",
}


def compare(original, rewrite):
    findings = []

    lit_o, rest_o = extract_literals(original)
    lit_r, rest_r = extract_literals(rewrite)
    sev_of = {kind: sev for kind, _p, sev in LITERAL_KINDS}
    rewrite_flat = _norm_ws(rewrite)
    for (kind, value), n in sorted((lit_o - lit_r).items()):
        if kind != "code-block" and value in rewrite_flat:
            if kind == "inline-code":
                findings.append({
                    "severity": "warn", "check": "literal.inline-code", "change": "unformatted",
                    "original": n, "rewrite": lit_r.get((kind, value), 0), "items": [value],
                    "message": "Value survived but lost its code formatting. A reader may no longer copy it exactly.",
                })
            continue
        findings.append({
            "severity": sev_of[kind], "check": f"literal.{kind}", "change": "missing",
            "original": n, "rewrite": lit_r.get((kind, value), 0), "items": [value],
            "message": "Literal missing or altered. Code, paths, flags, identifiers and codes must survive verbatim.",
        })
    for (kind, value), n in sorted((lit_r - lit_o).items()):
        if value in _norm_ws(original):
            continue
        findings.append({
            "severity": "warn" if kind == "quoted" else "error", "check": f"literal.{kind}",
            "change": "added", "original": lit_o.get((kind, value), 0), "rewrite": n, "items": [value],
            "message": "Literal not present in the original. A rewrite must not add identifiers or values.",
        })

    num_o, where_o = extract_numbers(rest_o)
    num_r, where_r = extract_numbers(rest_r)
    missing = num_o - num_r
    added = num_r - num_o
    if missing:
        findings.append({
            "severity": "error", "check": "number", "change": "missing",
            "original": sum(num_o.values()), "rewrite": sum(num_r.values()),
            "items": [f"{k} ×{v}  ← {where_o[k]}" for k, v in sorted(missing.items())],
            "message": "Number missing from the rewrite (values are normalized: 三 == 3 == three).",
        })
    if added:
        findings.append({
            "severity": "error", "check": "number", "change": "added",
            "original": sum(num_o.values()), "rewrite": sum(num_r.values()),
            "items": [f"{k} ×{v}  ← {where_r[k]}" for k, v in sorted(added.items())],
            "message": "Number not in the original. A rewrite must not add values.",
        })

    cat_o = extract_categories(rest_o)
    cat_r = extract_categories(rest_r)
    sev_cat = {name: sev for name, sev, _ in CATEGORIES}
    for name, _sev, _pats in CATEGORIES:
        n_o, hits_o = cat_o[name]
        n_r, hits_r = cat_r[name]
        if n_o == n_r:
            continue
        # Losing a marker widens or hardens the claim, so a decrease carries
        # the category's severity. Splitting one sentence into several often
        # repeats a marker ("if ... or otherwise" -> two "If" sentences), so an
        # increase is a warning, except for obligations: a new MUST or MUST NOT
        # is a new instruction.
        decreased = n_r < n_o
        severity = sev_cat[name] if decreased or name in GROWTH_IS_ERROR else "warn"
        findings.append({
            "severity": severity, "check": name,
            "change": "decreased" if decreased else "increased",
            "original": n_o, "rewrite": n_r,
            "items": (["original: " + h for h in hits_o[:6]] + ["rewrite:  " + h for h in hits_r[:6]]),
            "message": MESSAGES[name],
        })

    order = {"error": 0, "warn": 1}
    findings.sort(key=lambda f: (order[f["severity"]], f["check"]))
    return findings


def render(findings):
    errors = sum(f["severity"] == "error" for f in findings)
    warns = len(findings) - errors
    lines = [f"fidelity: {errors} error(s), {warns} warning(s)"]
    for f in findings:
        lines.append(f"\n{f['severity'].upper():5} {f['check']}  {f['change']}  "
                     f"(original {f['original']} → rewrite {f['rewrite']})")
        lines.append(f"      {f['message']}")
        for item in f["items"]:
            lines.append(f"      · {item}")
    if not findings:
        lines.append("No mechanical differences found. This does not prove the meaning is unchanged.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

SELFTEST = [
    # (name, original, rewrite, checks that must be errors, checks that must
    # not be errors). {"*"} as the last field means: no finding at all.
    ("identical text is clean",
     "If the job fails, retry 3 times. Do not use `--force`.",
     "If the job fails, retry 3 times. Do not use `--force`.", set(), {"*"}),
    ("dropped hedge is an error (en)",
     "The request may have failed.", "The request failed.",
     {"modal.possibility"}, set()),
    ("dropped hedge is an error (zh)",
     "请求可能已经失败。", "请求失败了。", {"modal.possibility"}, set()),
    ("Chinese numeral equals Arabic numeral",
     "如果超时，重试三次。", "如果超时，重试 3 次。", set(), {"number", "condition"}),
    ("dropped condition is an error",
     "如果超时，重试 3 次。", "重试 3 次。", {"condition"}, {"number"}),
    ("splitting a sentence may repeat 'if' without an error",
     "If the job fails or otherwise stalls, page the owner.",
     "If the job fails, page the owner. If the job stalls, page the owner.", set(), {"condition"}),
    ("不要 equals 不得 (both prohibit)",
     "注意不要删除正在写入的日志。", "不得删除正在写入的日志。", set(), {"modal.prohibit"}),
    ("如果…的话 equals …时，",
     "如果目标文件已存在的话，跳过。", "目标文件已存在时，跳过。", set(), {"condition"}),
    ("以下步骤 is not a bound",
     "清理日志目录。", "按以下步骤清理日志目录：", set(), {"scope.limit"}),
    ("最好不要 equals 不建议",
     "最好不要覆盖文件。", "不建议覆盖文件。", set(), {"modal.not-recommend", "modal.prohibit"}),
    ("90% 以上 is a bound",
     "使用率 90% 以上时，清理。", "使用率 ≥ 90% 时，清理。", set(), {"scope.limit"}),
    ("dropped 'Do not' is an error",
     "Do not run the migration twice.", "Run the migration twice.", {"modal.prohibit"}, set()),
    ("'does not match' is not a prohibition",
     "The format does not match.", "The format is different.", set(), {"modal.prohibit"}),
    ("lost upper bound is an error",
     "Retry at most 3 times.", "Retry 3 times.", {"scope.limit"}, {"number"}),
    ("dropped unless is an error",
     "Delete the cache unless the job is running.", "Delete the cache.", {"condition"}, set()),
    ("missing flag is an error",
     "Run `deploy --dry-run` first.", "Run deploy first.", {"literal.inline-code"}, set()),
    ("added number is an error",
     "Wait for the sync to finish.", "Wait 30 seconds for the sync to finish.", {"number"}, set()),
    ("MUST to SHOULD drift is an error",
     "调用方必须先获取令牌。", "建议调用方先获取令牌。", {"modal.require"}, set()),
    ("approximation removed is an error",
     "超时时间约 5 秒。", "超时时间是 5 秒。", {"modal.approx"}, {"number"}),
    ("应用 / 响应 are not modals",
     "应用会返回响应。", "应用返回响应。", set(), {"modal.require"}),
    ("added list numbering is not a number change",
     "Open the file, then read line 3.", "1. Open the file.\n2. Read line 3.", set(), {"number"}),
    ("不同 / 不仅 are not negations",
     "两个参数不同，不仅类型不一样。", "两个参数不同，类型不一样。", set(), {"modal.prohibit"}),
    ("prohibition lost is an error",
     "不得在生产环境运行此命令。", "在生产环境运行此命令前先备份。", {"modal.prohibit"}, set()),
    ("English number word equals digit",
     "Retry twice, then wait ten seconds.", "Retry 2 times. Then wait 10 seconds.", set(), {"number"}),
    ("an article 一个 is not a number",
     "读取一个配置文件。", "读取配置文件。", set(), {"number"}),
    ("path survives as plain text",
     "Edit `config/app.yaml`.", "Edit config/app.yaml.", set(), {"literal.path"}),
    ("trailing period is not part of a path",
     "Edit config/app.yaml.", "Open and edit config/app.yaml.", set(), {"literal.path", "literal.filename"}),
]


def selftest():
    failed = 0
    for name, original, rewrite, must_have, must_not in SELFTEST:
        got = {f["check"] for f in compare(original, rewrite) if f["severity"] == "error"}
        got_all = {f["check"] for f in compare(original, rewrite)}
        ok = must_have <= got
        if "*" in must_not:
            ok = ok and not got_all
        else:
            ok = ok and not (must_not & got)
        if not ok:
            failed += 1
            print(f"FAIL  {name}\n      expected errors {sorted(must_have)}, "
                  f"forbidden {sorted(must_not)}\n      got {sorted(got_all)}")
            print("      " + render(compare(original, rewrite)).replace("\n", "\n      "))
        else:
            print(f"ok    {name}")
    print(f"\n{len(SELFTEST) - failed}/{len(SELFTEST)} passed")
    return 1 if failed else 0


def _read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("original", nargs="?")
    ap.add_argument("rewrite", nargs="?")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="warnings also fail the run")
    ap.add_argument("--ignore", default="", help="comma-separated check names to skip (prefix match)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.original or not args.rewrite:
        ap.print_usage(sys.stderr)
        return 2
    if args.original == "-" and args.rewrite == "-":
        print("Only one of ORIGINAL/REWRITE can be stdin.", file=sys.stderr)
        return 2

    findings = compare(_read(args.original), _read(args.rewrite))
    ignore = [s.strip() for s in args.ignore.split(",") if s.strip()]
    findings = [f for f in findings if not any(f["check"].startswith(i) for i in ignore)]

    if args.json:
        print(json.dumps({"findings": findings}, ensure_ascii=False, indent=2))
    else:
        print(render(findings))
    failing = [f for f in findings if f["severity"] == "error" or args.strict]
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
