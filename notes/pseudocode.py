# ===== Common Interfaces =====
class Tool:
    def __init__(self, name, fn): self.name, self.fn = name, fn
    def __call__(self, **kwargs): return self.fn(**kwargs)

class Agent:
    def __init__(self, name, system_prompt, tools=None, memory=None):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = {t.name: t for t in (tools or [])}
        self.memory = memory or {}

    def call_llm(self, prompt, **kwargs):
        """
        伪函数：底层可用任意 LLM 调用。
        （在真实实现里，这里可接 OpenAI Responses/Agents SDK 的 agent loop）
        """
        # return llm(prompt=compose(self.system_prompt, prompt, self.memory), ...)
        ...

    def run(self, instruction, **kwargs):
        """
        agent loop（极简版）：
        - 让LLM决定是否调用工具/交接/返回
        - 这里用“结构化约定”的方式读LLM输出。例如：
          {"action": "tool:search", "args": {...}} / {"action": "handoff", "to": "Writer"} / {"action": "final", "content": "..."}
        """
        while True:
            decision = self.call_llm(instruction | kwargs | {"tools": list(self.tools)})
            if decision["action"].startswith("tool:"):
                tool_name = decision["action"].split("tool:")[1]
                result = self.tools[tool_name](**decision.get("args", {}))
                instruction = {"observation": result}
            elif decision["action"] == "handoff":
                return Handoff(target=decision["to"], payload=decision.get("payload", {}))
            elif decision["action"] == "final":
                return decision["content"]
            else:
                raise RuntimeError(f"Unknown action: {decision}")

class Handoff:
    def __init__(self, target, payload): self.target, self.payload = target, payload

# ===== Concrete Tools (示例) =====
def download_pdf(url): ...
def parse_pdf_to_struct(pdf_path): ...
def embed_and_search(query, kb_name, topk): ...
def make_plot(data_spec): ...
def save_to_kb(doc, kb_name): ...
def score_quality(summary, checks): ...  # 返回0-1

FetchTool   = Tool("fetch_pdf", download_pdf)
ParseTool   = Tool("parse_pdf", parse_pdf_to_struct)
SearchTool  = Tool("search_similar", embed_and_search)
PlotTool    = Tool("plot", make_plot)
SaveTool    = Tool("save_kb", save_to_kb)
ScoreTool   = Tool("score", score_quality)

# ===== Agents (同一模型，不同角色/工具/系统提示) =====
Planner = Agent(
    name="Planner",
    system_prompt="""
你是规划器。基于目标与上下文，输出下一步行动：
- 可选动作：调用工具、交接给[Fetcher|Parser|Retriever|Analyst|Writer|Critic]、或final。
- 在信息不足或质量不达标时，优先回到需要的步骤。
""",
    tools=[],
)

Fetcher = Agent(
    name="Fetcher",
    system_prompt="抓取器：输入为论文URL列表，下载PDF。输出本地路径与元数据。",
    tools=[FetchTool],
)

Parser = Agent(
    name="Parser",
    system_prompt="解析器：把PDF解析成结构化字段：title/abstract/sections/figures/refs。",
    tools=[ParseTool],
)

Retriever = Agent(
    name="Retriever",
    system_prompt="检索器：基于论文主题/关键词，检索相似论文topK，返回元数据与要点。",
    tools=[SearchTool],
)

Analyst = Agent(
    name="Analyst",
    system_prompt="""
分析师：比较新论文与相似论文：方法差异、数据集、SOTA指标、贡献/局限、是否新颖。
必要时可请求plot。
""",
    tools=[PlotTool],
)

Writer = Agent(
    name="Writer",
    system_prompt="""
写作者：产出结构化摘要：
- TL;DR（100-150字）
- 关键要点（3-5条）
- 方法/数据/指标
- 创新点 & 局限
- 与相关工作对比（引用）
- 复现要点
""",
    tools=[SaveTool],
)

Critic = Agent(
    name="Critic",
    system_prompt="""
评审：给出质量分q∈[0,1]并列出问题：
- 事实核对（与原文/引用一致？）
- 引用与链接是否齐全/可达？
- 结构是否完整？长度是否合规？
- 有无凭空捏造？
输出：{"q":0.0-1.0, "issues":[...], "action": "accept"|"revise", "revise_target":"Analyst|Writer|Retriever"}
""",
    tools=[ScoreTool],
)

AGENTS = {a.name: a for a in [Planner, Fetcher, Parser, Retriever, Analyst, Writer, Critic]}

# ===== Orchestrator（图式/状态机也可；此处给简单循环版） =====
def handoff(current_agent_name, handoff_obj):
    target = handoff_obj.target
    payload = handoff_obj.payload
    return AGENTS[target].run(payload)

def process_one_paper(url, kb_name, q_threshold=0.8, max_rounds=6):
    # 1) 让Planner起步
    step = AGENTS["Planner"].run({"goal": "总结并对比该论文", "input": {"url": url}})
    rounds = 0
    context = {}

    while rounds < max_rounds:
        rounds += 1
        if isinstance(step, Handoff):
            result = handoff("Planner", step)         # 转交
        else:
            result = step                              # 直接结果

        # 如果返回仍是handoff，继续接力
        if isinstance(result, Handoff):
            step = handoff(step.target, result)
            continue

        # 进入评审环节
        critique = AGENTS["Critic"].run({"summary": result, "checks": ["facts","refs","structure","length"]})
        if critique["action"] == "accept" and critique["q"] >= q_threshold:
            AGENTS["Writer"].tools["save_kb"](doc=result, kb_name=kb_name)
            return {"summary": result, "quality": critique["q"], "rounds": rounds}
        else:
            # 依据评审建议回修：可能回到Analyst或Writer或Retriever
            target = critique.get("revise_target", "Analyst")
            step = Handoff(target=target, payload={"summary": result, "issues": critique["issues"]})

    # 超过轮次仍未通过 → 给出最佳版本并标注未达标
    return {"summary": result, "quality": critique["q"], "rounds": rounds, "status": "timeout"}

def daily_job(hf_feed_url, kb_name):
    urls = fetch_todays_papers(hf_feed_url)  # 你已有的函数
    reports = []
    for url in urls:
        r = process_one_paper(url, kb_name)
        reports.append(r)
    return aggregate_daily_report(reports)    # 聚合日报：主题聚类/Top-K/趋势


"""
    关键点解释（落地时最容易踩坑的地方）

        为什么这是“代理实例”，不是“多个聊天窗口”？
        这些角色在同一编排器里运行，能handoff、共享/传递上下文、调用工具，并受同一停止条件/审计约束；
        不是人工切来切去。

        Plan-and-Execute 与质量门：Planner 可以按 Critic 的反馈改计划（例如“先补检索再写作”），
        这正是从“固定流水线”到“自决策”的跨越。

        可演进为图式编排：当你需要分支/并发/重入/可观测时，把上面 process_one_paper 换成
        “图/状态机”（LangGraph 或 AWS 的图式方案），利于生产运维。
"""