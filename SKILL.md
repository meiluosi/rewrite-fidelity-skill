---
name: rewrite-fidelity
description: "Use after any rewrite, simplification, or plain-language pass — English or Chinese — to check that the new text still says what the original said: same numbers, same code and identifiers, same conditions and exceptions, same requirement strength (MUST/SHOULD/MAY, 必须/建议/可以), same hedges (may have / 可能), same negations and scope. Pairs with asd-ste100, zh-disambiguate, jianming-zhongwen and any other rewrite skill. Triggers: check the rewrite, did the rewrite change the meaning, verify nothing was lost, fidelity check, 改写有没有改意思, 核对改写, 保真检查, 对比原文和改写稿. Not a style checker: it never judges whether the rewrite reads better."
version: 0.1.1
---

# Rewrite Fidelity

A simplifying rewrite has two ways to fail. It can stay hard to read, and style linters catch that. Or it can read well and say something different, and style linters cannot catch that, because they only see one text. This skill compares the original with the rewrite and looks for the second failure.

The costly changes are small. Dropping "may have" turns a guess into a fact. Dropping "unless" widens an instruction. Changing 应 to 建议 turns a requirement into advice. Changing "约 5 秒" to "5 秒" claims a precision the author did not have. Each of these makes the sentence shorter and cleaner, so a rewriter is tempted to make them.

## When to Use

- After you rewrite text with any simplification skill (asd-ste100, zh-disambiguate, jianming-zhongwen, or a plain request to "make this clearer").
- When the user asks whether a rewrite kept the meaning, or wants an audit of someone else's edit.
- Before you ship a rewritten tool description, error message, system prompt, or procedure.

Do not use it to judge style. It has no opinion about whether the rewrite reads better.

## Process

Run both passes. The script is fast and never forgets a number. The model pass catches what the script cannot see: a condition that is still present but now attaches to a different action, or a negation that moved to a different verb.

### Pass 1 — mechanical check

Save the original and the rewrite to two files, then run:

```bash
python3 scripts/fidelity.py original.txt rewrite.txt
```

The script compares:

| Check | What must match | Severity when lost |
|---|---|---|
| `literal.*` | code spans and blocks, URLs, paths, file names, flags, identifiers, error codes, versions — verbatim | error |
| `number` | every number, normalized (`三` = `3` = `three`, `百分之五` = `5`) | error, also when a number is **added** |
| `modal.require` / `modal.prohibit` | must, shall, Do not …, 必须, 应, 不得, 禁止, 不要 … | error in both directions |
| `modal.possibility` | may have, might, could, likely, 可能, 也许, 未必 … | error when lost |
| `modal.approx` | about, ~, 约, 大约, 左右 … | error when lost |
| `modal.not-recommend` / `modal.not-required` | should not, need not, 不建议, 不必 … | error when lost |
| `modal.not-recommend.soft` | had better not, 最好不要, 尽量不要 … | warning. Kept apart from `not-recommend` on purpose: in an agreement eval readers took 最好不要 as "default: no" but 不建议 as "left to the reader" |
| `condition` | if, unless, until, otherwise, before, 如果, 除非, 否则, 仅当, 之前 … | error when lost |
| `scope.limit` | at most, only, more than, 至少, 不超过, 仅, 3 次以上 … | error when lost |
| `negation` | not, never, without, 不, 没有, 未, 无 … | warning |
| `scope` | all, every, some, 所有, 每个, 部分 … | warning |
| `modal.recommend` / `permit` / `ability` / `may` | should, can, may, 建议, 可以, 能 … | warning |
| `literal.quoted` | "UI labels", 「错误原文」 | warning |

Errors exit 1. `--json` gives structured output. `--strict` also fails on warnings. `--ignore scope,negation` skips checks by name prefix.

A count that goes **up** is usually a split sentence that repeats "if" or "不". Read it, but expect it to be harmless. The exception is a new requirement or prohibition: that is a new instruction, so it stays an error.

### Pass 2 — claim check (model)

Matching counts do not prove matching meaning. "Retry unless the job is running" and "Run the job unless you retry" have the same markers. For each sentence of the original:

1. List its atomic claims: one actor, one action or state, plus its condition, scope, strength, and certainty. Write them as short lines, not prose.
2. Find each claim in the rewrite. Check that the condition still attaches to the same action, the negation to the same verb, and the scope word to the same noun.
3. Find each claim in the rewrite that has no source in the original. A new cause, frequency, actor, or mechanism is an added fact, even when it is probably true.

Go through the findings from Pass 1 one by one. For each one, say whether it is a real change or a harmless restructuring, and why.

### Output

Default output, when the user only wants a verdict:

```
Fidelity: <PASS | CHANGES FOUND>
- <check>: <original phrase> → <rewrite phrase>. <one-sentence consequence>.
```

List only real changes. Do not list harmless restructurings unless the user asks for the full audit. If there are changes, offer a corrected rewrite that keeps the improved style and restores the lost content. Do not revert to the original wording without a reason.

When the user asks for the full audit, add a table with one row for each original claim: `claim | found in rewrite | status (kept / changed / lost / added)`.

## Boundaries

**Will:**
- Report every number, literal, modal, condition, negation, and scope marker that the rewrite lost or added.
- Separate real meaning changes from harmless restructuring, and give a reason for each call.
- Suggest a fix that keeps the new style and restores the meaning.

**Will not:**
- Claim that a rewrite is meaning-preserving because the script found no differences. The script checks markers, not meaning. Say "no mechanical differences found" and then report the result of Pass 2.
- Judge readability, tone, or style.
- Treat a hedge as noise. "May have failed" and "failed" are different claims.
- Translate. The two texts must be in the same language. Mixed Chinese and English text is supported.

## Known Limits

- Regex heuristics, not a parser. Chinese single-character words (应, 能, 不, 无) are matched with exclusion lists (应用, 功能, 不同 …). Expect some false positives. Read the context snippet before you act on a finding.
- English "may" is both permission and possibility. The script counts it in its own bucket and leaves the decision to Pass 2.
- Units are not normalized: "30 s" and "30 秒" match on the value 30, and the script does not compare units.
- Bare 一 / 两 / one count as numbers only before time or size units, so that articles such as 一个 / a(n) are not counted as numbers.

## Additional Resources

- `scripts/fidelity.py` — the mechanical check. Stdlib only, Python 3.8+. `--selftest` runs the built-in cases.
- `examples/` — original/rewrite pairs with expected findings. `examples/run-examples.sh` runs them all.
- `references/integration.md` — how to call this check from asd-ste100, zh-disambiguate, or a CI job.
