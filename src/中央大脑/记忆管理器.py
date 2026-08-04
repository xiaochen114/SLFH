#!/usr/bin/env python3
"""记忆管理器 — 为 LLM 对话提供上下文记忆
   当前: 结构化决策历史拼接
   升级位: 未来可换 RAG/向量库，只改本文件"""
import json


class 记忆管理器:
    """管理 LLM 对话的上下文记忆，接口独立，可平滑升级"""

    def __init__(self, 数据库=None, 记忆条数=10):
        self._db = 数据库
        self._记忆条数 = 记忆条数  # 注入最近 N 条决策

    def 构建上下文(self, 对话内容=None, 额外=None):
        """拼装发给 LLM 的记忆上下文（历史决策 + 近期对话）"""
        段落 = []

        # 1. 历史决策记忆（来源: llm_decision 表）
        决策 = self._取决策记忆()
        if 决策:
            段落.append("## 系统最近的调度决策")
            段落.append(self._决策转文本(决策))

        # 2. 近期对话记忆
        对话 = self._取对话记忆()
        if 对话:
            段落.append("## 我们最近的对话")
            for d in 对话:
                role = "操作员" if d.get("role") == "operator" else "我"
                段落.append(f"- {role}: {d.get('content','')}")

        # 3. 当前输入
        if 对话内容:
            段落.append("## 现在操作员说")
            段落.append(对话内容)

        if 额外:
            段落.append("## 附加信息")
            段落.append(json.dumps(额外, ensure_ascii=False))

        return "\n".join(段落)

    def 取对话历史(self, limit=20):
        """返回最近对话（操作员+LLM），供前端展示"""
        if not self._db:
            return []
        对话 = self._db.查询对话(limit)
        return [
            {"role": d["role"], "content": d["content"],
             "time": d["created_at"], "orders": d["orders_json"]}
            for d in 对话
        ]

    # ---- 内部 ----

    def _取决策记忆(self):
        if not self._db:
            return []
        return self._db.查询LLM决策(self._记忆条数)

    def _取对话记忆(self):
        if not self._db:
            return []
        return self._db.查询对话(10)

    @staticmethod
    def _决策转文本(决策列表):
        """把 llm_decision 记录转成可读文本"""
        行 = []
        for d in 决策列表:
            mode = "LLM" if d.get("mode") == "llm" else "规则"
            事件 = [f"{e.get('label') or e.get('type','?')}(等级{e.get('level',0)})"
                    for e in d.get("events_json", [])][:3]
            指令 = [f"{o.get('type','?')}->{o.get('robot_id','?')}" if isinstance(o, dict)
                    else str(o) for o in d.get("orders_json", [])][:3]
            行.append(
                f"- [{mode}] " +
                ("事件:" + ",".join(事件) if 事件 else "无事件") +
                (" → 指令:" + ",".join(指令) if 指令 else " → 无指令")
            )
        return "\n".join(行) if 行 else "(暂无决策记录)"
