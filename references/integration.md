# Integration

## From another rewrite skill

Add one step at the end of the rewrite skill's process. The wording below fits asd-ste100's `## Process` section after step 4. The same text works for zh-disambiguate and jianming-zhongwen.

```markdown
5. If the rewrite-fidelity skill is installed, save the original and the rewrite to two files and run
   `python3 <rewrite-fidelity>/scripts/fidelity.py original.txt rewrite.txt`.
   Fix every error-level finding that is a real meaning change. Then do the claim check in
   rewrite-fidelity's SKILL.md (Pass 2). Do not show this check to the user unless they asked for it.
```

The step says "if installed" so the host skill still works without it.

### Proposed upstream issue for asd-ste100

asd-ste100's README says that its linter does not compare the original with the rewrite and cannot prove that meaning was preserved. This skill fills that gap. A short issue or PR to `danyuchn/asd-ste100-skill` could say:

> The README notes that ste-lint.py checks one text and cannot confirm that a rewrite preserved meaning or requirement strength. rewrite-fidelity (link) compares the original with the rewrite. It checks numbers, literals, conditions, negation, scope bounds, and modality (MUST/SHOULD/MAY and hedges such as "may have"). It is stdlib-only, like ste-lint.py. Would you accept an optional Process step that calls it when it is installed? Proposed wording: (step above).

## In CI

The script exits 1 on error-level findings, so it can gate a pull request that rewrites docs. Keep the pre-rewrite text from the base branch:

```yaml
- name: Fidelity check on rewritten tool descriptions
  run: |
    for f in $(git diff --name-only origin/main -- 'tools/*.md'); do
      git show origin/main:"$f" > /tmp/original.md || continue
      python3 rewrite-fidelity/scripts/fidelity.py /tmp/original.md "$f"
    done
```

This only makes sense for a pull request whose purpose is to rewrite text. A pull request that changes behavior also changes the facts, and the check will report those changes as errors.

## As a library

```python
from fidelity import compare   # scripts/ on sys.path
findings = compare(original_text, rewrite_text)
errors = [f for f in findings if f["severity"] == "error"]
```

Each finding is a dict with these keys: `severity`, `check`, `change`, `original`, `rewrite`, `items`, `message`.
