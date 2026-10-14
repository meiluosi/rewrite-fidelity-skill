# rewrite-fidelity：改写保真检查

对比原文和改写稿，找出丢失或改动的数字、代码、条件、否定、上下限、阈值方向、比较方向、断言强度与情态强度。可作为 Claude Code skill 使用，也可单独运行 Python 脚本；支持中文和英文。

[English](#english) · [安装与第一次使用](#安装与第一次使用) · [完整示例](examples/README.md) · [局限](#局限)

## 「最多 3 次」变成「3 次」，会查出什么

| 原文 | 改写稿 |
|---|---|
| 重试最多 3 次。 | 重试 3 次。 |

用仓库中的 `scripts/fidelity.py` 检查这两句话，实际输出为：

```text
fidelity: 1 error(s), 0 warning(s)

ERROR scope.limit  decreased  (original 1 → rewrite 0)
      Bound or limit changed (at most/only/至少/不超过/以上). A lost bound turns a limit into an exact value or removes it.
      · original: 重试[最多] 3 次。
```

数字 3 还在，但上限「最多」消失了。脚本报告 `scope.limit` 错误，并以退出码 1 结束。

**这是机械检查，不能证明语义相同。**例如，[条件脱离动作的示例](examples/zh-detached-condition)保留了所有标记，脚本仍返回 0 个错误。skill 还要求模型逐条核对原文中的事实。

## 安装与第一次使用

安装 Claude Code skill：

```bash
npx skills add meiluosi/rewrite-fidelity-skill
```

或者：

```bash
git clone https://github.com/meiluosi/rewrite-fidelity-skill ~/.claude/skills/rewrite-fidelity
```

在 Claude Code 里提供两版文本：

```text
用 rewrite-fidelity 核对这次改写有没有改变意思。

原文：重试最多 3 次。
改写稿：重试 3 次。
```

也可以说「核对一下这次改写有没有改意思」或 “Check that the rewrite kept the meaning”，并附上原文和改写稿。

### 直接运行脚本

只依赖 Python 3.8+ 标准库。先获取仓库，再创建两份文本，即可复现上面的输出：

```bash
git clone https://github.com/meiluosi/rewrite-fidelity-skill
cd rewrite-fidelity-skill
printf '%s\n' '重试最多 3 次。' > original.txt
printf '%s\n' '重试 3 次。' > rewrite.txt
python3 scripts/fidelity.py original.txt rewrite.txt
```

检测到 error 时退出码为 1。其他常用命令：

```bash
python3 scripts/fidelity.py --json original.txt rewrite.txt
python3 scripts/fidelity.py --selftest
sh examples/run-examples.sh
```

## 它查什么

简化改写最容易丢的，往往是让句子显得啰嗦、但承载意思的那几个词：

| 原文 | 改写 | 意思的变化 |
|---|---|---|
| 请求**可能已经**失败 | 请求失败了 | 推测变成了事实 |
| **除非**迁移已完成，**不建议**使用 `--skip-migrate` | 不要使用 --skip-migrate | 条件丢了，建议变成了禁令，代码格式也丢了 |
| 超时**约** 5 秒 | 超时 5 秒 | 声称了原文没有的精度 |
| 重试**最多** 3 次 | 重试 3 次 | 上限变成了确切次数 |
| 调用方**必须**先获取令牌 | 建议调用方先获取令牌 | MUST 降成了 SHOULD |

脚本 `scripts/fidelity.py` 抽取两份文本中的以下内容，比较哪些丢了、哪些是新加的：

- **原样字面量**：代码、URL、路径、命令参数、标识符、错误码、版本号
- **数字**：归一化后比较，`三` = `3` = `three`，`百分之五` = `5`
- **情态强度**：要求、禁止、建议、允许、能力、可能性、约数。中文按 GB/T 1.1 的能愿动词分组，英文按 RFC 2119 加上 hedge 词分组
- **条件和例外**：如果、除非、否则、仅当、之前 / if、unless、otherwise、before
- **否定**、**范围和上下限**：所有、仅、至少、不超过、以上 / all、only、at least
- **阈值方向**：词和符号归为同一组（`以上` = `≥`，`不超过` = `≤`，`超过` = `>`）。`不超过 200 元` 改成 `超过 200 元`、`at least` 改成 `at most`、`p < 0.05` 改成 `p > 0.05`，总数不变，但方向翻了，算 error；`90% 以上` 改成 `≥ 90%` 不算
- **比较方向**：「A 比 B 好 / A 优于 B」改成「B 比 A 好」算 error。只处理两个对象之间的比较，阈值不归这里管
- **断言强度**：改写稿里多出「证明、必然、显然、proves、definitely」算 error；多出「总是、完全、一定、always」只给警告（「不一定」是 hedge，「绝对值」是术语，不计入）

脚本只做机械检查，计数一致不代表意思一致（见 [`examples/zh-detached-condition`](examples/zh-detached-condition)）。所以 SKILL.md 还要求模型做第二遍检查：把原文拆成原子事实，逐条在改写稿里找对应。

## 为什么要比较两份文本

asd-ste100、jianming-zhongwen 这类简化写作 skill 自带的 linter 只看一份文本，检查句子形式。它们无法比较原文和改写稿，因此需要另一步检查改写是否改变了意思。本项目提供这一步检查。

## 和其他 skill 配合

本项目是 [asd-ste100](https://github.com/danyuchn/asd-ste100-skill)、[zh-disambiguate](https://github.com/meiluosi/zh-disambiguate-skill)、[jianming-zhongwen](https://github.com/heichaowo/jianming-zhongwen) 等改写 skill 的后置检查。接入方法和 CI 用法见 [`references/integration.md`](references/integration.md)。

## 局限

- 规则基于正则，不是语法分析器。「应」「能」「不」这类单字靠排除表（应用、功能、不同……）来减少误报，不能完全避免。
- 英文的 may 既可以表示允许，也可以表示可能。脚本把它单独计数，具体是哪种交给模型判断。
- 只比较数值，不比较单位。
- 阈值方向靠词表匹配：词表之外的写法（「不到」「no greater than」）不会被计数，只涉及这类词的翻转看不见。比较方向只读标记词两侧的一小段，长句或嵌套句看不到。断言强度只数词，分不清「加强了断言」和「换了一个强调词」。
- 不做翻译检查。原文和改写稿必须是同一种语言，中英混排可以。

## 许可证

MIT

---

## English

Compare an original with its rewrite to find lost or altered numbers, code, conditions, negations, bounds, threshold and comparison direction, claim strength, and requirement strength. Use it as a Claude Code skill or a standalone Python script. It supports English and Chinese.

### A result you can reproduce

Changing `重试最多 3 次。` (“Retry at most 3 times.”) to `重试 3 次。` (“Retry 3 times.”) keeps the number but drops the upper bound. The script reports `ERROR scope.limit`, with 1 error, 0 warnings, and exit code 1. The exact output is [shown above](#最多-3-次变成3-次会查出什么).

### Install and try

```bash
npx skills add meiluosi/rewrite-fidelity-skill
```

Or install into Claude Code's skills directory:

```bash
git clone https://github.com/meiluosi/rewrite-fidelity-skill ~/.claude/skills/rewrite-fidelity
```

Then provide both texts in Claude Code:

```text
Use rewrite-fidelity to check whether this rewrite changed the meaning.

Original: Retry at most 3 times.
Rewrite: Retry 3 times.
```

The standalone script needs only Python 3.8+ and its standard library. Clone the repository, enter its directory, and compare two UTF-8 files:

```bash
python3 scripts/fidelity.py original.txt rewrite.txt   # exit 1 on error-level findings
python3 scripts/fidelity.py --json original.txt rewrite.txt
```

### What it checks

Style linters such as asd-ste100's `ste-lint.py` check one text. This skill compares two: the original and the rewrite. It reports lost or added literals (code, paths, flags, identifiers, versions), numbers (normalized across `3` / `three` / `三`), requirement strength (MUST / SHOULD / MAY, 必须 / 建议 / 可以), hedges (may have, 可能), approximations (about, 约), conditions (unless, 除非), negations, and scope bounds (at most, 不超过). It also checks threshold direction (words and symbols share one bucket, so `以上` → `≥` is fine but `不超过` → `超过` or `p < 0.05` → `p > 0.05` is an error), comparison direction ("A is better than B" reversed), and claim strength ("suggests" → "proves" is an error; softer words such as "always" only warn).

The script is the mechanical first pass. [SKILL.md](SKILL.md) adds a model pass that compares the texts one atomic claim at a time. Markers can all survive while a condition moves to a different action; [`examples/zh-detached-condition`](examples/zh-detached-condition) shows a bad rewrite that produces 0 script errors.

The rules use regular expressions and can produce false positives. English “may” needs contextual interpretation. Numeric checks do not compare units. This is not a translation checker: both texts must use the same language, though mixed Chinese/English text is supported.

See the [examples](examples/README.md) and [integration guide](references/integration.md) for use with rewriting skills and CI.

