"""公文文种定义。

依据《党政机关公文处理工作条例》的法定文种，取国企与政府日常使用频率
最高的九种。每种文种的结构、结束语、主送对象、写作要求都不同，
生成流程据此驱动，而不是写死一套「请示」结构。

direction 用于区分行文方向，前端据此调整主送机关示例与字段可见性。
"""

from typing import Dict, List, Optional

# 行文方向
UP = "up"            # 上行文：报上级
DOWN = "down"        # 下行文：发下级
PARALLEL = "parallel"  # 平行文：平级商洽
INTERNAL = "internal"  # 内部记载

DIRECTION_LABEL = {
    UP: "上行文",
    DOWN: "下行文",
    PARALLEL: "平行文",
    INTERNAL: "内部文件",
}


DOC_TYPES: Dict[str, dict] = {
    # ---------------------------------------------------------------- 上行
    "request": {
        "name": "请示",
        "direction": UP,
        "usage": "向上级请求指示或批准",
        "recipient": "公司领导：",
        "title_suffix": "的请示",
        "title_hint": "关于申请采购办公设备的请示",
        "sections": ["事由", "依据", "请示事项"],
        "closing": "妥否，请批示。",
        "needs_procurement": True,
        "prompt_hint": (
            "一文一事，只请示一个事项。事由要说明背景与必要性，"
            "依据要引用具体制度条款，请示事项要具体明确、可直接批复。"
            "语气恳切，不得夹带报告内容。"
        ),
    },
    "report": {
        "name": "报告",
        "direction": UP,
        "usage": "向上级汇报工作、反映情况",
        "recipient": "公司领导：",
        "title_suffix": "的报告",
        "title_hint": "关于 2026 年度信息化建设情况的报告",
        "sections": ["基本情况", "主要工作与成效", "存在问题", "下一步打算"],
        "closing": "特此报告。",
        "needs_procurement": False,
        "prompt_hint": (
            "情况真实、数据准确，成效要有具体支撑，问题不回避不淡化，"
            "下一步措施要可落地。报告不得夹带请示事项，"
            "如需上级批准应另行文请示。"
        ),
    },
    # ---------------------------------------------------------------- 下行
    "notice": {
        "name": "通知",
        "direction": DOWN,
        "usage": "向下级布置工作、传达事项",
        "recipient": "各部门、各子公司：",
        "title_suffix": "的通知",
        "title_hint": "关于开展年度安全生产检查的通知",
        "sections": ["事由", "具体事项", "工作要求"],
        "closing": "特此通知。",
        "needs_procurement": False,
        "prompt_hint": (
            "发文缘由简明，事项分条列出、边界清楚，"
            "工作要求写明责任主体、完成时限与反馈方式。"
            "涉及多部门协同时明确牵头单位。"
        ),
    },
    "circular": {
        "name": "通报",
        "direction": DOWN,
        "usage": "表彰先进、批评错误、传达重要情况",
        "recipient": "各部门：",
        "title_suffix": "的通报",
        "title_hint": "关于表彰 2026 年度先进集体的通报",
        "sections": ["情况概述", "主要事迹或问题", "决定事项", "要求"],
        "closing": "特此通报。",
        "needs_procurement": False,
        "prompt_hint": (
            "表彰类突出具体事迹与可学的精神，批评类讲清问题性质与教训，"
            "决定事项明确（表彰名单、处理意见），"
            "最后对全体提出针对性要求。"
        ),
    },
    "reply": {
        "name": "批复",
        "direction": DOWN,
        "usage": "答复下级机关的请示事项",
        "recipient": "××部门：",
        "title_suffix": "的批复",
        "title_hint": "关于同意采购办公设备的批复",
        "sections": ["来文引述", "批复意见", "执行要求"],
        "closing": "此复。",
        "needs_procurement": False,
        "prompt_hint": (
            "开头引述来文标题与文号（如「你部门《关于……的请示》收悉」），"
            "然后明确表态：同意、原则同意或不同意，不同意要说明理由，"
            "最后提出执行中的具体要求。态度明确，不含糊。"
        ),
    },
    "decision": {
        "name": "决定",
        "direction": DOWN,
        "usage": "对重要事项作出决策和部署",
        "recipient": "各部门：",
        "title_suffix": "的决定",
        "title_hint": "关于设立数字化转型工作专班的决定",
        "sections": ["决定缘由", "决定事项", "执行要求"],
        "closing": "",
        "needs_procurement": False,
        "prompt_hint": (
            "缘由充分，说明作出决定的背景与依据；"
            "决定事项明确具体，涉及机构、人员、职责、奖惩的写清范围和标准；"
            "执行要求写明生效时间与责任主体。语气庄重果断。"
        ),
    },
    "opinion": {
        "name": "意见",
        "direction": DOWN,
        "usage": "对重要问题提出见解和处理办法",
        "recipient": "各部门：",
        "title_suffix": "的意见",
        "title_hint": "关于加强合同全流程管理的意见",
        "sections": ["背景与依据", "总体要求", "主要任务", "保障措施"],
        "closing": "",
        "needs_procurement": False,
        "prompt_hint": (
            "针对具体问题提出系统性解决办法，"
            "总体要求点明指导思想与目标，主要任务分条列项、有抓手，"
            "保障措施落到组织、经费、考核上。兼具原则性与可操作性。"
        ),
    },
    # ---------------------------------------------------------------- 平行
    "letter": {
        "name": "函",
        "direction": PARALLEL,
        "usage": "平级机关之间商洽工作、询问答复",
        "recipient": "××单位：",
        "title_suffix": "的函",
        "title_hint": "关于商请协助办理办公场所租赁手续的函",
        "sections": ["事由", "商洽事项", "结语"],
        "closing": "请予支持为盼。",
        "needs_procurement": False,
        "prompt_hint": (
            "平级商洽，不用指令性语气，用「商请」「请予支持」「盼复」等表述。"
            "事项具体、边界清楚，便于对方判断和回复。"
            "答复类函开头引述来函。"
        ),
    },
    # ---------------------------------------------------------------- 内部
    "minutes": {
        "name": "纪要",
        "direction": INTERNAL,
        "usage": "记载会议主要情况和议定事项",
        "recipient": "",
        "title_suffix": "会议纪要",
        "title_hint": "数字化转型专题会议纪要",
        "sections": ["会议概况", "议定事项"],
        "closing": "",
        "needs_procurement": False,
        "prompt_hint": (
            "会议概况写清时间、地点、主持人、参会人员与议题；"
            "议定事项是重点，用「会议决定」「会议同意」「会议要求」表述，"
            "客观记录，不掺杂个人评价，事项要具体可执行、责任到部门。"
        ),
    },
}

# 兼容旧数据的默认值
DEFAULT_DOC_TYPE = "request"


def get_doc_type(code: Optional[str]) -> dict:
    """取文种配置，未知值回落到请示。"""
    return DOC_TYPES.get(code or DEFAULT_DOC_TYPE, DOC_TYPES[DEFAULT_DOC_TYPE])


def doc_type_name(code: Optional[str]) -> str:
    return get_doc_type(code)["name"]


def section_names(code: Optional[str]) -> List[str]:
    return get_doc_type(code)["sections"]


def section_names_with_suffix(code: Optional[str]) -> List[str]:
    """分段生成用的段落名，如「事由段落」。"""
    return [f"{s}段落" for s in get_doc_type(code)["sections"]]


def list_doc_types() -> List[dict]:
    """供前端渲染文种选择器。"""
    out = []
    for code, cfg in DOC_TYPES.items():
        out.append({
            "code": code,
            "name": cfg["name"],
            "direction": cfg["direction"],
            "direction_label": DIRECTION_LABEL.get(cfg["direction"], ""),
            "usage": cfg["usage"],
            "recipient": cfg["recipient"],
            "title_suffix": cfg["title_suffix"],
            "title_hint": cfg["title_hint"],
            "sections": cfg["sections"],
            "closing": cfg["closing"],
            "needs_procurement": cfg["needs_procurement"],
        })
    return out


def is_valid(code: Optional[str]) -> bool:
    return bool(code) and code in DOC_TYPES
