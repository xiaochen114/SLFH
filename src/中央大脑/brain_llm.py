#!/usr/bin/env python3
"""LLM 调度引擎 — 接入大模型 API 做智能调度决策
   降级：API 不可用时回退规则模式，后台自动重连"""
import json, time, os, threading, urllib.request, urllib.error

from 机器人.robot_base import RobotOrder

# 大模型 API 配置（OpenAI 兼容格式）
API_URL = os.environ.get("LLM_API_URL", "http://10.122.4.100:31277/inference-api/exp-api/inf-1512399859630841856/v1/chat/completions")
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "YbhkjOUt66kpdoTSmK4PPqqBbqTgYnTwioUkQupssmg")
API_MODEL = os.environ.get("LLM_API_MODEL", "default")

# 降级参数
LLM_TIMEOUT = 8          # 单次请求超时(秒)，防止调度循环卡死
失败降级阈值 = 2          # 连续失败 N 次后进入降级模式
重连间隔 = 30             # 降级模式下每 N 秒尝试重连

系统提示词 = """你是一个多机器人调度系统的决策引擎。根据当前状态输出调度指令。

## 机器人类型
- dog: 陆地巡逻/火情确认  (移动速度慢，续航长)
- drone: 空中侦察/通信中继 (移动速度快，续航短)

## 指令类型
- patrol: 开始巡逻 {point: 巡逻点名}（目标点从"可用巡逻点"中选择）
- stop: 停止当前动作
- alert: 急停/警戒
- return: 返回/回零
- inspect: 检查指定位置 {target: [x, y]}
- custom: 自定义指令 {command: "xxx"}

## 可用巡逻点
上下文中会提供"可用巡逻点"列表（名称+坐标）。需要派机器人去某个位置时，优先用巡逻点里的坐标。若列表为空则不可巡逻。

## 决策规则
1. 低电量(<20%) → return
2. 发现火情(fire_detected) 且附近有机器人 → alert + inspect
3. 通信断连(comm_level≥2) → 派 drone 中继
4. 空闲机器人(idle) → patrol（选一个巡逻点作为目标）

## 输出格式
返回 JSON 数组，每个元素: {"type":"指令类型","robot_id":"机器人ID","params":{},"priority":0-3}
没有需要执行的指令时返回空数组 []
"""


class LLM调度引擎:
    """LLM 调度引擎 — 优先 LLM，失败降级规则，后台自动重连"""

    def __init__(self, api_url=None, api_key=None, api_model=None, 数据库=None, mode="auto"):
        self._api_url = api_url or API_URL
        self._api_key = api_key or API_KEY
        self._api_model = api_model or API_MODEL
        self._db = 数据库
        self._mode = mode  # auto / rule / llm
        self._连续失败 = 0
        self._降级中 = False
        self._最后错误 = ""
        self._最后成功 = 0
        self._重连线程 = None

    # ---- 状态 ----

    def 获取状态(self) -> dict:
        """当前 LLM 连接状态（前端展示用）"""
        return {
            "mode": "rule" if self._降级中 else "llm",
            "降级中": self._降级中,
            "连续失败": self._连续失败,
            "最后错误": self._最后错误,
            "最后成功": self._最后成功,
        }

    def _保存状态(self):
        if self._db:
            try:
                self._db.保存配置("llm_status", self.获取状态())
            except:
                pass

    def _进入降级(self, error):
        self._降级中 = True
        self._最后错误 = str(error)[:200]
        print(f"[LLM] 降级到规则模式: {error}")
        self._保存状态()
        # 启动后台重连线程（只启动一次）
        if not self._重连线程 or not self._重连线程.is_alive():
            self._重连线程 = threading.Thread(target=self._重连循环, daemon=True)
            self._重连线程.start()

    def _恢复(self):
        if self._降级中:
            print("[LLM] API 恢复，切回 LLM 模式")
        self._降级中 = False
        self._连续失败 = 0
        self._最后成功 = time.time()
        self._保存状态()

    def _重连循环(self):
        """降级模式下周期性尝试重连"""
        while self._降级中:
            time.sleep(重连间隔)
            try:
                # 轻量探测：不发真实调度请求，直接问一次
                self._llm决策({"robots": [], "events": []})
                self._恢复()
            except Exception as e:
                self._最后错误 = str(e)[:200]
                self._保存状态()

    def 决策(self, context: dict) -> list:
        """
        根据全局状态做决策
        context: {robots: [...], events: [...]}
        返回: RobotOrder 列表
        """
        if self._mode == "rule" or self._降级中:
            return self._规则决策(context)

        # 尝试 LLM API
        try:
            if self._api_key:
                orders = self._llm决策(context)
                if orders is not None:
                    self._恢复()
                    return orders
        except Exception as e:
            self._连续失败 += 1
            self._最后错误 = str(e)[:200]
            if self._连续失败 >= 失败降级阈值:
                self._进入降级(e)
            else:
                print(f"[LLM] 调用失败({self._连续失败}/{失败降级阈值}): {e}")

        # 降级到规则
        return self._规则决策(context)

    # ======================== LLM 决策 ========================

    def _llm决策(self, context: dict, system=None) -> list:
        """调用 DeepSeek API 生成调度指令。system 可传自定义系统提示词"""
        # 构建上下文
        robots = context.get("robots", [])
        events = context.get("events", [])
        patrol_points = context.get("patrol_points", [])

        robot_lines = []
        for r in robots:
            robot_lines.append(
                f"- {r.get('id','?')} ({r.get('type','?')}) "
                f"电量={r.get('battery',0)*100:.0f}% "
                f"模式={r.get('mode','?')} 健康={r.get('health','?')} "
                f"通信L{r.get('comm_level',3)}"
            )

        event_lines = [f"- {e.get('type','?')}: {json.dumps(e, ensure_ascii=False)}" for e in events]

        # 巡逻点列表
        point_lines = []
        for p in patrol_points:
            point_lines.append(
                f"- {p.get('name','点'+str(p.get('index',0)+1))}: 坐标({p.get('x','?')}, {p.get('y','?')}) 朝向{p.get('yaw',0)}"
            )

        prompt = f"""## 当前机器人状态
{chr(10).join(robot_lines) if robot_lines else "(无在线机器人)"}

## 当前事件
{chr(10).join(event_lines) if event_lines else "(无事件)"}

## 可用巡逻点
{chr(10).join(point_lines) if point_lines else "(暂无巡逻点)"}

请输出调度指令 JSON。"""

        # 调用 API
        body = json.dumps({
            "model": self._api_model,
            "messages": [
                {"role": "system", "content": system or 系统提示词},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 1024,
        }).encode()

        req = urllib.request.Request(
            self._api_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        resp = urllib.request.urlopen(req, timeout=LLM_TIMEOUT)
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
            rid = o.get("robot_id", "")
            if isinstance(rid, dict):  # 防 LLM 返回嵌套结构
                rid = rid.get("id", "") or ""
            orders.append(RobotOrder(
                order_id=f"llm_{int(time.time())}_{len(orders)}",
                type=o.get("type", "custom"),
                robot_id=rid if isinstance(rid, str) else "",
                params=o.get("params", {}),
                priority=o.get("priority", 0),
                source="brain",
            ))
        print(f"[LLM] 生成 {len(orders)} 条调度指令")
        return orders

    def 对话(self, prompt, system=None):
        """操作员对话：返回结构化 {reply, orders}。orders 不直接下发"""
        对话提示词 = system or """你是调度大脑，回答操作员的调度问题。
只输出 JSON 对象: {"reply": "你的回答", "orders": [{"type":"指令类型","robot_id":"机器人ID","params":{},"priority":0-3}]}
orders 仅在需要执行操作时填，不需要则空数组。回复要简洁中文。"""
        try:
            body = json.dumps({
                "model": self._api_model,
                "messages": [
                    {"role": "system", "content": 对话提示词},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0, "max_tokens": 512,
            }).encode()
            req = urllib.request.Request(
                self._api_url, data=body,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self._api_key}"},
                method="POST")
            resp = urllib.request.urlopen(req, timeout=LLM_TIMEOUT)
            raw = json.loads(resp.read().decode())
            content = raw["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(content)
            return {
                "reply": parsed.get("reply", ""),
                "orders": parsed.get("orders", []) or [],
            }
        except Exception as e:
            print(f"[LLM] 对话失败: {e}")
            return {"reply": "", "orders": [], "error": str(e)}

    # ======================== 规则决策（降级） ========================

    def _规则决策(self, context: dict) -> list:
        """基于规则的备用决策器"""
        orders = []
        events = context.get("events", [])
        robots = context.get("robots", [])
        patrol_points = context.get("patrol_points", [])

        def 找空闲(类型=None):
            """从在线机器人里挑一个（可限定类型），返回 robot_id"""
            for r in robots:
                if not r.get("id"):
                    continue
                if r.get("health") != "ok":
                    continue
                if 类型 and r.get("type") != 类型:
                    continue
                return r.get("id")
            return ""

        for ev in events:
            etype = ev.get("type", "")
            if etype == "fire_detected":
                # 派狗急停 + 无人机去火点侦察
                狗id = 找空闲("dog")
                无人机id = 找空闲("drone")
                if 狗id:
                    orders.append(RobotOrder(
                        f"rule_{int(time.time())}_1", "alert",
                        狗id, {"reason": "fire"}, priority=3, source="brain"))
                if 无人机id:
                    orders.append(RobotOrder(
                        f"rule_{int(time.time())}_2", "inspect",
                        无人机id, {"target": ev.get("position", (0, 0))},
                        priority=2, source="brain"))
            elif etype == "smoke_detected":
                # 派狗去最近的巡逻点巡查（有巡逻点则用坐标）
                狗id = 找空闲("dog")
                point = patrol_points[0] if patrol_points else None
                params = {"speed": 10000}
                if point:
                    params["target"] = [point.get("x", 0), point.get("y", 0)]
                    params["point"] = point.get("name", "")
                if 狗id:
                    orders.append(RobotOrder(
                        f"rule_{int(time.time())}_3", "patrol",
                        狗id, params, priority=1, source="brain"))
            elif etype == "communication_lost":
                无人机id = 找空闲("drone")
                if 无人机id:
                    orders.append(RobotOrder(
                        f"rule_{int(time.time())}_4", "custom",
                        无人机id,
                        {"command": "fly_to_relay",
                         "target": ev.get("position", (0, 0))},
                        priority=2, source="brain"))

        # 低电量巡检
        for r in robots:
            bat = r.get("battery", 1)
            rid = r.get("id", "")
            if rid and bat < 0.2 and r.get("mode") != "returning":
                orders.append(RobotOrder(
                    f"rule_{int(time.time())}_bat", "return",
                    rid, {}, priority=2, source="brain"))

        return orders


