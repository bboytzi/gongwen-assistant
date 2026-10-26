"""逐句引用溯源。

正文是纯文本，生成时并没有记录「哪句话来自哪份材料」。这里用字符 n-gram
覆盖率做回溯匹配：

  句子被某份材料「覆盖」的比例 = 句子中的 2-gram 有多少出现在该材料里

选覆盖率而不是 Jaccard，是因为材料是 500 字左右的分块，而句子往往只用到
其中一小部分，Jaccard 会被长材料拉低。

标题命中（如句中提到《采购管理办法》）额外加分，这类显式引用比字面重合更可靠。
"""

import re
from typing import Dict, List, Optional

# 中文按句末标点切分，保留标点
_SENT_SPLIT = re.compile(r"(?<=[。！？；!?;])")
_PARA_SPLIT = re.compile(r"\n+")
_WS = re.compile(r"\s+")
# 文件名里的扩展名与括号备注，匹配标题时去掉
_TITLE_CLEAN = re.compile(r"[（(].*?[)）]|\.(pdf|docx?|txt)$", re.IGNORECASE)

MIN_SENTENCE_LEN = 6        # 太短的句子（如「妥否，请批示。」）不参与匹配
DEFAULT_THRESHOLD = 0.32    # 覆盖率阈值
TITLE_BONUS = 0.35          # 标题命中的加分


def _ngrams(text: str, n: int = 2) -> set:
    s = _WS.sub("", text)
    if len(s) < n:
        return set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def _coverage(sentence: str, source: str) -> float:
    """句子里的 2-gram 有多少比例出现在 source 中。"""
    s = _ngrams(sentence)
    if not s:
        return 0.0
    r = _ngrams(source)
    if not r:
        return 0.0
    return len(s & r) / len(s)


def _title_core(title: str) -> str:
    if not title:
        return ""
    t = _TITLE_CLEAN.sub("", title).strip()
    # 只保留前 12 个字做匹配，避免长文件名干扰
    return t[:12]


def split_paragraphs(content: str) -> List[List[str]]:
    """按段落切，段内按句切。返回 [[句, 句], [句], ...]。"""
    paragraphs = []
    for raw in _PARA_SPLIT.split(content or ""):
        raw = raw.strip()
        if not raw:
            continue
        sentences = [p.strip() for p in _SENT_SPLIT.split(raw) if p.strip()]
        if sentences:
            paragraphs.append(sentences)
    return paragraphs


def build_citations(
    content: str,
    references: List[Dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> Dict:
    """生成逐句溯源结果。

    返回：
      {
        "paragraphs": [
          [{"text": "...", "ref_index": 0, "score": 0.71, "via": "content"}, ...],
          ...
        ],
        "cited_count": 12,
        "sentence_count": 40,
      }
    """
    refs = references or []
    prepared = []
    for i, r in enumerate(refs):
        prepared.append({
            "index": i,
            "title_core": _title_core(r.get("title", "")),
            "content": r.get("content", "") or "",
        })

    paragraphs_out = []
    cited = 0
    total = 0

    for para in split_paragraphs(content):
        out_para = []
        for sent in para:
            total += 1
            entry = {"text": sent, "ref_index": None, "score": 0.0, "via": None}

            # 短句不参与匹配，但仍要返回以保持正文完整
            if len(_WS.sub("", sent)) >= MIN_SENTENCE_LEN and prepared:
                best_idx: Optional[int] = None
                best_score = 0.0
                best_via = None

                for p in prepared:
                    score = _coverage(sent, p["content"])
                    via = "content"

                    core = p["title_core"]
                    if core and core in sent:
                        score += TITLE_BONUS
                        via = "title"

                    if score > best_score:
                        best_score = score
                        best_idx = p["index"]
                        best_via = via

                if best_idx is not None and best_score >= threshold:
                    entry["ref_index"] = best_idx
                    entry["score"] = round(best_score, 3)
                    entry["via"] = best_via
                    cited += 1

            out_para.append(entry)
        paragraphs_out.append(out_para)

    return {
        "paragraphs": paragraphs_out,
        "cited_count": cited,
        "sentence_count": total,
        "reference_count": len(refs),
    }
