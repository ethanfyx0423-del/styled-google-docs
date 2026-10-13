---
name: styled-google-docs
description: 用 Google Docs/Drive 连接器新建文档时使用：一步生成排版精致的中英混排文档，按内容自动选“编辑部杂志风”或“学术典雅风”。
---

# 设计感 Google Docs（Styled Google Docs）

用 Google Drive / Google Docs 连接器**新建**文档时，用这套流程直接产出排版好的成品，而不是 Docs 默认的 Arial 样式。适用于课程笔记、报告、方案、计划、会议纪要等；用户明确指定别的字体或样式时，以用户为准。

开始前先读 `anthropic-skills:google-workspace` 的 `references/docs.md`：那里的通用规则（修订号保护、索引、写作规范）仍然适用。

## 1. 选风格

| 风格 | theme | 用于 | 气质 |
|---|---|---|---|
| A 编辑部杂志风 | `editorial` | 学习/课程笔记、读书笔记、计划、会议纪要、日常记录 | Playfair Display 标题 + Source Serif 4 正文 + Noto Serif SC 中文；细线分隔、暗红强调色 #8C2F25 |
| C 学术典雅风 | `academic` | 报告、方案、研究分析、正式提交的文档 | EB Garamond + Noto Serif SC；标题居中、摘要、三线表、方框“命题/要点”，深蓝强调色 #1F3A5F |

用户没指定时按上表判断；拿不准时用 `editorial`。两套共用同一套规则：A4 纸、页边距 60/56/66/66 pt、中英文分别设字体、颜色只用在编号和要点上。

## 2. 流程（每份文档都走完这 5 步）

**第 1 步：把内容写成轻量 Markdown**（存为 `doc.md`），语法：

```
::kicker 课程名 · WEEK 05            （editorial 用：标题上方的小字栏目）
# 文档标题
::subtitle 英文副标题或一句话说明
::meta 课程笔记　·　2026 年 10 月 13 日　·　Ethan
::abstract 摘要 Abstract. | 摘要正文       （academic 用）

## 1 一级标题 English Title             （开头的编号 1 / 1.1 / I. 会自动上强调色，可省略）
正文段落，支持 **加粗** 和 *斜体*（斜体只用于英文）。

- 无序列表项
1. 有序列表项

::callout 要点 Takeaway | 一句话结论      （editorial：上下强调色细线；academic：细线方框）
### 1.1 二级标题
::caption 表 1　表格标题
| 列 A | 列 B | 数值 |
|---|---|---|
| … | … | 12.0% |
::source 数据来源：…
> 一句引文
::footer 页脚小字
```

写作要求：块之间空一行；不要手打列表符号以外的编号符号（•、①）；中文不要用斜体；表格里纯数字列会自动右对齐。内容本身仍遵守 docs.md 的 Writing 规则。

**第 2 步：生成 HTML。** 脚本在本 skill 目录的 `scripts/gdoc_style.py`（下文写作 `<skill>/scripts/gdoc_style.py`）：

```
python <skill>/scripts/gdoc_style.py html doc.md --theme editorial --out out     # 可加 --accent "#1F4E5F"
```

得到 `out/doc.html` 和 `out/manifest.json`。

**第 3 步：创建文档。** Drive `create_file`，`title` = 文档标题，`contentMimeType: "text/html"`，`textContent` = `out/doc.html` 的完整内容（Read 该文件后原样传入，不要手改）。记下返回的文件 id。

**第 4 步：修正排版（必须做）。** Drive 的 HTML 导入会把中文字体换成 Arial、丢掉段落边框、纸张设成 Letter，所以要补一轮：

1. Docs `read_doc` 读新文档。结果通常太大会被存成文件，记下路径。
2. `python <skill>/scripts/gdoc_style.py fix <read_doc 结果路径> --manifest out/manifest.json --out fix.json`
   - 终端应显示 `matched N/N paragraphs`。没全匹配时看 skipped 行，多半是正文里有导入器改写的字符；修正 doc.md 后从第 2 步重来，或接受未匹配段落用默认样式。
3. 把 `fix.json` 里的 `requests` 和 `writeControl` 原样传给一次 `update_doc`。被拒（修订号不符）就重读、重跑 fix、重发。

**第 5 步：检查。** Drive `download_file_content`（`exportMimeType: application/pdf`），用 google-workspace 的 `scripts/render_export.py` 渲染成图片并查看：中文是否都是宋体（Noto Serif SC）而不是黑体/Arial、加粗是否生效、分隔线和方框是否在、表格有无溢出。有问题就修，修完再看。

最后在回复里给出文档链接（标题做成链接），一句话说明用了哪种风格。页码需要的话告诉用户用“插入 > 页码”（API 加不了）。

## 3. 设计规格（修改已有文档、或脚本不可用时手工照此设置）

通用：纸张 A4（595.28 × 841.89 pt），边距上 60、下 56、左右 66 pt。中文字符一律 `Noto Serif SC`（加粗时 weight 700，且去掉斜体），英文/数字用该风格的拉丁字体。

**A · editorial**（墨色 #1C1B19，次要文字 #5C5852，细线 #D9D5CE，强调色 #8C2F25）

| 角色 | 字体/字号 | 段落 |
|---|---|---|
| kicker | Source Serif 4，8pt 粗体，大写，强调色 | 下框线 0.75pt 墨色，padding 5，段后 16 |
| 标题 | 中文 Noto Serif SC 700 / 英文 Playfair Display，30pt | TITLE 样式，行距 110%，段后 4 |
| 副标题 | Playfair Display 斜体 14pt，#4A4742 | 段后 14 |
| meta | 9pt，#5C5852 | 上下框线 0.75pt #D9D5CE，段后 24 |
| H2 / H3 | Playfair + Noto Serif SC 粗体 18 / 13pt，编号用强调色 | 段前 24 / 16，段后 8 / 6，与下段同页 |
| 正文 / 列表 | Source Serif 4 11pt | 行距 160%，段后 8 / 3 |
| 要点 | 标签 8pt 粗体强调色 + 正文 14pt | 标签上框线 1.5pt 强调色；正文下框线 0.75pt 强调色 |
| 表格 | 10pt，表头粗体 | 表头上 1pt、下 0.75pt 墨色；行间 0.75pt #E6E2DB；末行 1pt 墨色；无竖线 |
| 引文 | Playfair 斜体 16pt | 居中，左右缩进 40 |

**C · academic**（墨色 #1A1A1A，次要 #4A4A4A，强调色 #1F3A5F）

| 角色 | 字体/字号 | 段落 |
|---|---|---|
| 标题 | Noto Serif SC 400 / EB Garamond，24pt | TITLE，居中 |
| 副标题 / meta | EB Garamond 斜体 13pt / 11pt 灰 | 居中 |
| 摘要 | 11pt，标签粗体 | 两端对齐，左右缩进 30，行距 140% |
| H2 / H3 | 粗体 15 / 12.5pt，编号用强调色 | 段前 20 / 14，与下段同页 |
| 正文 | EB Garamond 12pt | 两端对齐，首行缩进 24pt，行距 150% |
| 列表 | 有序列表用小写罗马数字 | 行距 150% |
| 命题/要点框 | 12pt，标签粗体，英文部分斜体 | 四边 0.75pt 墨色框线 |
| 表格（三线表） | 11pt，标题居中置于表上 | 顶线 1.5pt、表头下 0.75pt、底线 1.5pt，其余无线 |
| 来源 | 9pt 灰 | 居中 |

## 4. 已验证的限制

- HTML 导入不认中文网络字体（变 Arial）和段落边框（会变成多余的水平线），所以 HTML 里不写段落边框，统一由第 4 步的 API 补上；API 设置 `Noto Serif SC` 有效。
- 小数字号会被取整（8.5→8），字距（letter-spacing）不支持。
- 表格无法通过 API 居中，宽度占满版心。
- 页码、真正的脚注不能经 HTML 导入生成：页码让用户手动插入；参考文献用文末列表。
- 此流程只用于**新建**。修改用户已有文档时按 docs.md 的 Editing 规则做最小改动，新增内容按第 3 节规格匹配文档已有风格，不要整篇重排，除非用户要求。
