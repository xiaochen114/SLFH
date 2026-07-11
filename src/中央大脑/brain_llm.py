#!/usr/bin/env python3
"""LLM 调度引擎 — 接入 DeepSeek API 做智能调度决策
   支持降级：API 不可用时回退到规则模式"""
import json, time, os, urllib.request, urllib.error

from 机器人.robot_base import RobotOrder

# DeepSeek API (兼容 OpenAI 格式)
API_URL = os.environ.get("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

系统提示词 = """你是一个多机器人调度系统的决策引擎。根据当前状态输出调度指令。

## 机器人类型
- dog: 陆地巡逻/火情确认  (移动速度慢，续航长)
- drone: 空中侦察/通信中继 (移动速度快，续航短)

## 指令类型
- patrol: 开始巡逻
- stop: 停止当前动作
- alert: 急停/警戒
- return: 返回/回零
- inspect: 检查指定位置 {target: [x, y]}
- custom: 自定义指令 {command: "xxx"}

## 决策规则
1. 低电量(<20%) → return
2. 发现火情(fire_detected) 且附近有机器人 → alert + inspect
3. 通信断连(comm_level≥2) → 派 drone 中继
4. 空闲机器人(idle) → patrol

## 输出格式
返回 JSON 数组，每个元素: {"type":"指令类型","robot_id":"机器人ID","params":{},"priority":0-3}
没有需要执行的指令时返回空数组 []
"""


class LLM调度引擎:
    """LLM 调度引擎 — 可切换规则/API 模式"""

    def __init__(self, api_key=None, mode="auto"):
        self._api_key = api_key or API_KEY
        self._mode = mode  # auto / rule / llm
        self._fallback_count = 0

    def 决策(self, context: dict) -> list:
        """
        根据全局状态做决策
        context: {robots: [...], events: [...]}
        返回: RobotOrder 列表
        """
        if self._mode == "rule":
            return self._规则决策(context)

        # 尝试 LLM API
        try:
            if self._api_key:
                orders = self._llm决策(context)
                if orders is not None:
                    self._fallback_count = 0
                    return orders
        except Exception as e:
            print(f"[LLM] API 调用失败: {e}")

        # 降级到规则
        self._fallback_count += 1
        if self._fallback_count == 1:
            print("[LLM] API 不可用，降级到规则模式")
        return self._规则决策(context)

    # ======================== LLM 决策 ========================

    def _llm决策(self, context: dict) -> list:
        """调用 DeepSeek API 生成调度指令"""
        # 构建上下文
        robots = context.get("robots", [])
        events = context.get("events", [])

        robot_lines = []
        for r in robots:
            robot_lines.append(
                f"- {r.get('id','?')} ({r.get('type','?')}) "
                f"电量={r.get('battery',0)*100:.0f}% "
                f"模式={r.get('mode','?')} 健康={r.get('health','?')} "
                f"通信L{r.get('comm_level',3)}"
            )

        event_lines = [f"- {e.get('type','?')}: {json.dumps(e, ensure_ascii=False)}" for e in events]

        prompt = f"""## 当前机器人状态
{chr(10).join(robot_lines) if robot_lines else "(无在线机器人)"}

## 当前事件
{chr(10).join(event_lines) if event_lines else "(无事件)"}

请输出调度指令 JSON。"""

        # 调用 API
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": 系统提示词},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
        }).encode()

        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())

        content = result["choices"][0]["message"]["content"]
        # 解析 JSON（可能被 markdown 包裹）
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        raw_orders = json.loads(content)
        if not isinstance(raw_orders, list):
            return []

        orders = []
        for o in raw_orders:
            orders.append(RobotOrder(
                order_id=f"llm_{int(time.time())}_{len(orders)}",
                type=o.get("type", "custom"),
                params=o.get("params", {}),
                priority=o.get("priority", 0),
                source="brain",
            ))
        print(f"[LLM] 生成 {len(orders)} 条调度指令")
        return orders

    # ======================== 规则决策（降级） ========================

    def _规则决策(self, context: dict) -> list:
        """基于规则的备用决策器"""
        orders = []
        events = context.get("events", [])
        robots = context.get("robots", [])

        for ev in events:
            etype = ev.get("type", "")
            if etype == "fire_detected":
                orders.append(RobotOrder(
                    f"rule_{int(time.time())}_1", "alert",
                    {"reason": "fire"}, priority=3, source="brain"))
                for r in robots:
                    if r.get("type") == "drone" and r.get("health") == "ok":
                        orders.append(RobotOrder(
                            f"rule_{int(time.time())}_2", "inspect",
                            {"target": ev.get("position", (0, 0))},
                            priority=2, source="brain"))
                        break
            elif etype == "smoke_detected":
                orders.append(RobotOrder(
                    f"rule_{int(time.time())}_3", "patrol",
                    {"speed": 10000}, priority=1, source="brain"))
            elif etype == "communication_lost":
                for r in robots:
                    if r.get("type") == "drone" and r.get("health") == "ok":
                        orders.append(RobotOrder(
                            f"rule_{int(time.time())}_4", "custom",
                            {"command": "fly_to_relay",
                             "target": ev.get("position", (0, 0))},
                            priority=2, source="brain"))
                        break

        # 低电量巡检
        for r in robots:
            bat = r.get("battery", 1)
            if bat < 0.2 and r.get("mode") != "returning":
                orders.append(RobotOrder(
                    f"rule_{int(time.time())}_bat", "return",
                    {}, priority=2, source="brain"))

        return orders


