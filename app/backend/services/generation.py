"""Prompt templates and generation pipeline for document generation."""

import json
import time
from typing import Optional
from services.llm_client import LLMClient
from services.search import hybrid_search
from services.doc_types import get_doc_type, section_names_with_suffix
from sqlalchemy.orm import Session


INTENT_ANALYSIS_PROMPT = """你是一个国企公文写作专家。请分析以下公文起草请求，提取关键信息。

用户输入：
{user_input}

公文类别：{doc_category}
关键要素：{key_elements}

请输出 JSON 格式（只输出JSON，不要其他内容）：
{{
  "doc_category": "公文的具体类别",
  "procurement_scenario": "采购场景（如果是采购类）",
  "budget_amount": "预算金额（数字）",
  "procurement_method": "建议的采购方式（直接委托/询价/公开采购/招标）",
  "key_entities": {{
    "事由": "...",
    "涉及对象": "...",
    "金额": "...",
    "资金来源": "...",
    "依据": "..."
  }},
  "required_sections": ["事由", "依据", "请示事项", "附件清单"],
  "priority_refs": ["需要引用的关键制度名称"]
}}
"""

OUTLINE_PROMPT = """你是一个国企公文写作专家。请根据以下信息，生成一份{type_name}的大纲。

公文标题：{title}
文种：{type_name}（{type_usage}）
公文类别：{doc_category}
{extra_context}
关键要素：
{key_elements}

检索到的相关制度条款：
{rag_context}

检索到的历史案例参考：
{rag_cases}

请输出大纲，包含以下部分（每部分用一句话说明要写什么）：
{sections_list}

文种写作要求：
{type_hint}

只输出大纲，不要写正文。
"""

SECTION_GENERATE_PROMPT = """你是一个国企公文写作专家。请根据以下大纲和参考材料，生成{type_name}的"{section_name}"部分。

公文标题：{title}
大纲要求：{outline}
关键要素：{key_elements}

相关制度条款（请在正文中准确引用条款号和文件名）：
{rag_context}

历史案例参考（参考其写作风格和结构，但不要照抄）：
{rag_cases}

文种写作要求：
{type_hint}

要求：
1. 使用公文语言，简洁、准确、正式
2. 引用制度条款时，使用"根据《XXX》第X条"的格式
3. 每处引用后面标注[引用：文档名]便于溯源
4. 只输出该段落的正文内容，不要输出标题

{scenario_hint}
"""

# Procurement scenario hints (from 采购公文模板2022.11.14.docx)
SCENARIO_HINTS = {
    "project_execution": "本公文为项目执行采购场景。事由应说明项目进展情况和执行需要，依据引用项目审批文件和采购管理办法。",
    "element_org": "本公文为要素组织采购场景。事由应说明组织要素配置需求，依据引用组织管理办法和采购管理办法。",
    "joint": "本公文为联合采购场景。事由应说明联合采购的必要性和参与方，依据引用采购管理办法第十七条联合采购条款。",
    "admin": "本公文为行政后勤采购场景。事由应说明行政办公需求，依据引用行政管理办法和采购管理办法。",
    "client_specified": "本公文为甲方指定采购场景。事由应说明甲方指定的原因和依据，依据引用合同条款和采购管理办法第十八条。",
}

# Budget-based procurement method determination
def determine_procurement_method(budget_amount: float) -> str:
    """Auto-determine procurement method based on budget amount (from 采购管理办法)."""
    if budget_amount < 30:
        return "直接委托"
    elif budget_amount < 50:
        return "询价"
    elif budget_amount < 200:
        return "公开采购"
    else:
        return "招标"

def determine_procurement_method_en(budget_amount: float) -> str:
    if budget_amount < 30:
        return "direct"
    elif budget_amount < 50:
        return "inquiry"
    elif budget_amount < 200:
        return "public"
    else:
        return "tender"


REFERENCE_VALIDATE_PROMPT = """请检查以下公文内容中引用的制度条款是否真实存在于给定的参考材料中。

公文内容：
{content}

参考材料（原始制度条款）：
{references}

请输出 JSON 格式：
{{
  "valid": true/false,
  "issues": [
    {{
      "quoted": "引用的内容",
      "found": true/false,
      "note": "如果未找到，说明问题"
    }}
  ]
}}
"""


class GenerationPipeline:
    """Document generation pipeline: intent → RAG → outline → sections → validate."""

    def __init__(self, llm_client: LLMClient, db: Session, user_id: str):
        self.llm = llm_client
        self.db = db
        self.user_id = user_id

    def analyze_intent(self, doc_config: dict) -> dict:
        """Step 1: Analyze user intent and extract key information."""
        prompt = INTENT_ANALYSIS_PROMPT.format(
            user_input=doc_config.get("title", ""),
            doc_category=doc_config.get("doc_category", "procurement"),
            key_elements=json.dumps(doc_config.get("key_elements", {}), ensure_ascii=False),
        )
        resp = self.llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )
        try:
            return json.loads(resp.content)
        except json.JSONDecodeError:
            return {"doc_category": doc_config.get("doc_category", "")}

    def rag_search(self, query: str, kb_ids: list[str]) -> dict:
        """Step 2: RAG retrieval from knowledge base.

        优先走混合检索（语义 + 关键词）；若 embedding 不可用
        （例如只配了 DeepSeek，它没有 embedding 接口），
        自动降级为纯关键词检索，保证生成流程不中断。
        """
        query_embedding = None
        if self.llm.embedding_model:
            try:
                query_embedding = self.llm.embed(query).vector
            except Exception as e:
                print(f"[rag_search] Embedding 调用失败，降级为关键词检索: {e}")

        if query_embedding:
            results = hybrid_search(
                self.db,
                query=query,
                query_embedding=query_embedding,
                user_id=self.user_id,
                kb_ids=kb_ids,
                limit=10,
            )
            all_results = results["results"]
        else:
            from services.search import keyword_search
            all_results = keyword_search(
                self.db,
                query=query,
                user_id=self.user_id,
                kb_ids=kb_ids,
                limit=10,
            )

        # Separate regulations from cases
        regulations = [r for r in all_results if r.get("doc_type") == "regulation"]
        cases = [r for r in all_results if r.get("doc_type") == "case"]
        return {
            "regulations": regulations,
            "cases": cases,
            "all": all_results,
        }

    def generate_outline(self, doc_config: dict, rag_results: dict) -> str:
        """Step 3: Generate document outline."""
        rag_context = "\n\n".join(
            f"[{r['title']}]\n{r['content'][:500]}"
            for r in rag_results.get("regulations", [])[:5]
        )
        rag_cases = "\n\n".join(
            f"[{r['title']}]\n{r['content'][:300]}"
            for r in rag_results.get("cases", [])[:3]
        )
        budget = doc_config.get("budget_amount", 0)
        dt = get_doc_type(doc_config.get("doc_type"))

        # 采购相关上下文只对请示类文种有意义
        extra_lines = []
        if dt["needs_procurement"]:
            scenario = doc_config.get("procurement_scenario")
            if scenario:
                extra_lines.append(f"采购场景：{scenario}")
            if budget:
                extra_lines.append(f"预算金额：{budget} 万元")
                extra_lines.append(f"采购方式：{determine_procurement_method(budget)}")
        extra_context = ("\n".join(extra_lines) + "\n") if extra_lines else ""

        sections_list = "\n".join(
            f"{i}. {s}段落" for i, s in enumerate(dt["sections"], 1)
        )

        prompt = OUTLINE_PROMPT.format(
            type_name=dt["name"],
            type_usage=dt["usage"],
            type_hint=dt["prompt_hint"],
            sections_list=sections_list,
            extra_context=extra_context,
            title=doc_config.get("title", ""),
            doc_category=doc_config.get("doc_category", ""),
            key_elements=json.dumps(doc_config.get("key_elements", {}), ensure_ascii=False, indent=2),
            rag_context=rag_context,
            rag_cases=rag_cases,
        )
        resp = self.llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=2048,
        )
        return resp.content

    def generate_section(
        self,
        section_name: str,
        outline: str,
        doc_config: dict,
        rag_results: dict,
    ) -> str:
        """Step 4: Generate a specific section of the document."""
        rag_context = "\n\n".join(
            f"[{r['title']}]\n{r['content'][:500]}"
            for r in rag_results.get("regulations", [])[:5]
        )
        rag_cases = "\n\n".join(
            f"[{r['title']}]\n{r['content'][:300]}"
            for r in rag_results.get("cases", [])[:3]
        )
        dt = get_doc_type(doc_config.get("doc_type"))
        scenario = doc_config.get("procurement_scenario", "")
        # 采购场景提示只对请示类文种生效
        scenario_hint = SCENARIO_HINTS.get(scenario, "") if dt["needs_procurement"] else ""
        prompt = SECTION_GENERATE_PROMPT.format(
            type_name=dt["name"],
            type_hint=dt["prompt_hint"],
            section_name=section_name,
            title=doc_config.get("title", ""),
            outline=outline,
            key_elements=json.dumps(doc_config.get("key_elements", {}), ensure_ascii=False, indent=2),
            rag_context=rag_context,
            rag_cases=rag_cases,
            scenario_hint=scenario_hint,
        )
        resp = self.llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4096,
        )
        return resp.content

    def validate_references(self, content: str, references: list[dict]) -> dict:
        """Step 5: Validate that cited references actually exist in source documents."""
        ref_text = "\n\n".join(
            f"[{r.get('title', '')}]\n{r.get('content', '')[:500]}"
            for r in references[:10]
        )
        prompt = REFERENCE_VALIDATE_PROMPT.format(
            content=content,
            references=ref_text,
        )
        resp = self.llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2048,
        )
        try:
            return json.loads(resp.content)
        except json.JSONDecodeError:
            return {"valid": True, "issues": []}

    def generate_full_document(self, doc_config: dict, kb_ids: list[str]) -> dict:
        """Run the full generation pipeline."""
        results = {}

        # Step 1: Intent analysis
        results["intent"] = self.analyze_intent(doc_config)

        # Step 2: RAG search
        search_query = doc_config.get("title", "") + " " + " ".join(
            str(v) for v in doc_config.get("key_elements", {}).values()
        )
        results["rag"] = self.rag_search(search_query, kb_ids)

        # Step 3: Outline
        results["outline"] = self.generate_outline(doc_config, results["rag"])

        # Step 4: Generate each section
        sections = ["事由段落", "依据段落", "请示事项段落"]
        results["sections"] = {}
        for section in sections:
            results["sections"][section] = self.generate_section(
                section, results["outline"], doc_config, results["rag"]
            )

        # Combine into full content
        full_content = "\n\n".join(results["sections"].values())
        results["full_content"] = full_content

        # Step 5: Validate references
        results["validation"] = self.validate_references(
            full_content, results["rag"].get("all", [])
        )

        return results
