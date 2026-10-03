# Examples

Each folder holds an `original.txt`, a `rewrite.txt`, and the exit code that `scripts/fidelity.py` must return (`expected-exit`). `run-examples.sh` checks all of them.

| Folder | Rewrite quality | Script result | What it shows |
|---|---|---|---|
| `en-good-split` | good | 0 errors, 2 warnings | Splitting one sentence repeats "if" and adds "not". The count goes up, so the script warns but does not fail. |
| `en-hedge-promoted` | bad | 3 errors | "may have occurred" → "failed", "could be caused by" → "causes", "at most 3 times" → "3 times", "before" dropped. |
| `zh-good-split` | good | 0 errors, 1 warning | Restructured into two sentences. `除非 … 否则` adds one condition marker. |
| `zh-meaning-drift` | bad | 4 errors | 可能、大约、不建议、除非、否则 all dropped. 不建议 became 不要 (advice became a ban). |
| `zh-detached-condition` | **bad** | **0 errors** | `除非所有迁移都已经手动完成。` became its own sentence. Every marker survived, but the condition no longer attaches to the instruction. Only the Pass 2 claim check in SKILL.md finds this. |

The last example is the reason SKILL.md requires both passes.
