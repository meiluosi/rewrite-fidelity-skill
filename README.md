# rewrite-fidelity：改写保真检查

[English](#english)

一个 Claude Code skill，检查改写稿有没有改变原文的意思。支持中文和英文。

asd-ste100、jianming-zhongwen 这类简化写作 skill 自带的 linter 只看一份文本，检查的是句子形状。它们不能比较原文和改写稿，所以发现不了这种情况：改写稿读起来更顺了，说的却已经不是同一件事。asd-ste100 的 README 也写明了这一点。本项目补的就是这个缺口。

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

脚本只做机械检查，计数一致不代表意思一致（见 [`examples/zh-detached-condition`](examples/zh-detached-condition)）。所以 SKILL.md 还要求模型做第二遍检查：把原文拆成原子事实，逐条在改写稿里找对应。

## 安装

```bash
npx skills add meiluosi/rewrite-fidelity-skill
```

或者：

```bash
git clone https://github.com/meiluosi/rewrite-fidelity-skill ~/.claude/skills/rewrite-fidelity
```

## 使用

在 Claude Code 里直接说：

```
核对一下这次改写有没有改意思
Check that the rewrite kept the meaning
```

也可以单独运行脚本，只依赖 Python 3.8+ 标准库：

```bash
python3 scripts/fidelity.py original.txt rewrite.txt          # 有 error 时退出码为 1
python3 scripts/fidelity.py --json original.txt rewrite.txt
python3 scripts/fidelity.py --selftest
sh examples/run-examples.sh
```

## 和其他 skill 配合

本项目是 [asd-ste100](https://github.com/danyuchn/asd-ste100-skill)、[zh-disambiguate](https://github.com/meiluosi/zh-disambiguate-skill)、[jianming-zhongwen](https://github.com/heichaowo/jianming-zhongwen) 等改写 skill 的后置检查。接入方法和 CI 用法见 [`references/integration.md`](references/integration.md)。

## 局限

- 规则基于正则，不是语法分析器。「应」「能」「不」这类单字靠排除表（应用、功能、不同……）来减少误报，不能完全避免。
- 英文的 may 既可以表示允许，也可以表示可能。脚本把它单独计数，具体是哪种交给模型判断。
- 只比较数值，不比较单位。
- 不做翻译检查。原文和改写稿必须是同一种语言，中英混排可以。

## 许可证

MIT

---

## English

A Claude Code skill that checks whether a rewrite still says what the original said. It works on English and Chinese text.

Style linters such as asd-ste100's `ste-lint.py` check one text. This skill compares two: the original and the rewrite. It reports lost or added literals (code, paths, flags, identifiers, versions), numbers (normalized across `3` / `three` / `三`), requirement strength (MUST / SHOULD / MAY, 必须 / 建议 / 可以), hedges (may have, 可能), approximations (about, 约), conditions (unless, 除非), negations, and scope bounds (at most, 不超过).

The script is the mechanical first pass. SKILL.md adds a model pass that compares the texts one atomic claim at a time. Markers can all survive while a condition moves to a different action. `examples/zh-detached-condition` shows a case where this happens.

```bash
python3 scripts/fidelity.py original.txt rewrite.txt   # exit 1 on error-level findings
```
