#!/usr/bin/env python3
"""运维自愈 — 规则诊断优先，LLM增强，低危自动修复，高危人工确认"""
import os, sys, time, json, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class 高危闸门:
    """两级闸门：低危自动、高危人工"""
    高危关键字 = [
        "reboot", "shutdown", "systemctl stop", "systemctl disable",
        "rm ", "rm -rf", "mkfs", "fdisk", "ip link set",
        "nmcli con delete", "apt remove", "pip uninstall",
        "kill -9", "pkill -9",
    ]

    def 判断(self, 命令):
        命令 = 命令.lower()
        for kw in self.高危关键字:
            if kw in 命令:
                return True
        return False


class 运维自愈:
    def __init__(self, 事件总线=None, 数据库=None, llm=None, 注册中心=None):
        self._诊断器 = {}
        self._事件总线 = 事件总线
        self._db = 数据库
        self._llm = llm
        self._注册中心 = 注册中心
        self._闸门 = 高危闸门()
        self._待确认 = []
        self._历史 = []
        self._锁 = threading.Lock()
        if 事件总线:
            事件总线.订阅("robot_issue", self.处理事件)

    def 注册诊断器(self, 设备类型, 诊断器):
        self._诊断器[设备类型] = 诊断器
        print(f"[自愈] 已注册诊断器: {设备类型}")
        self._记录("注册诊断器", {"设备类型": 设备类型})

    def 获取诊断器列表(self):
        return list(self._诊断器.keys())

    def 处理事件(self, 事件):
        """触发自愈诊断（后台线程，不阻塞事件发布）"""
        robot_id = 事件.get("data", {}).get("robot_id", "")
        symptom = 事件.get("data", {}).get("message", "")
        设备类型 = self._查设备类型(robot_id)
        if not 设备类型 or 设备类型 not in self._诊断器:
            print(f"[自愈] 无诊断器: {robot_id}({设备类型})")
            return
        print(f"[自愈] 触发: {robot_id}({设备类型}) - {symptom}")
        # 后台执行，SSH 诊断可能耗时，不阻塞主流程
        threading.Thread(
            target=self._执行诊断链, args=(设备类型, robot_id, symptom),
            daemon=True,
        ).start()

    def _查设备类型(self, robot_id):
        if self._注册中心:
            r = self._注册中心.获取机器人(robot_id)
            if r:
                try:
                    st = r.get_status()
                    if st.robot_type == "dog":
                        return "绝影"
                except:
                    pass
        if "绝影" in str(robot_id) or "dog" in str(robot_id).lower():
            return "绝影"
        if "感知" in str(robot_id) or "103" in str(robot_id):
            return "感知主机"
        return None

    def _执行诊断链(self, 设备类型, robot_id, symptom):
        诊断器 = self._诊断器[设备类型]
        ssh_cfg = 诊断器.get("ssh", {})
        检查列表 = 诊断器.get("检查", [])
        修复列表 = 诊断器.get("修复", [])
        验证列表 = 诊断器.get("验证", [])
        诊断日志 = {"robot": robot_id, "symptom": symptom, "步骤": []}

        for 检查 in 检查列表:
            名称 = 检查["名称"]
            命令 = 检查["命令"].format(host=ssh_cfg.get("host", ""))
            结果 = self._执行命令(ssh_cfg, 命令)
            诊断日志["步骤"].append({"检查": 名称, "命令": 命令, "结果": str(结果)[:200]})
            self._记录("诊断_" + 名称, {"robot": robot_id, "命令": 命令, "结果": str(结果)[:200]})
            for 修复 in 修复列表:
                if 修复["匹配"] in str(结果):
                    self._执行修复(修复, ssh_cfg, robot_id, 验证列表)
                    return
        # 规则无结论 → LLM增强
        if not any(r["匹配"] in str(x.get("结果", "")) for x in 诊断日志["步骤"] for r in 修复列表):
            llm建议 = self._LLM诊断(设备类型, 诊断日志)
            if llm建议:
                self._执行修复(llm建议, ssh_cfg, robot_id, 验证列表)

    def _执行修复(self, 修复, ssh_cfg, robot_id, 验证列表=None):
        动作 = 修复["动作"]
        # 高危判定: 诊断器声明的高危 或 闸门关键字命中
        是否高危 = 修复.get("级别") == "高危" or self._闸门.判断(动作)
        if 是否高危:
            with self._锁:
                self._待确认.append({"动作": 动作, "robot": robot_id, "时间": time.time()})
            self._记录("高危待确认", {"robot": robot_id, "动作": 动作})
            print(f"[自愈] 高危待确认: {动作}")
        else:
            print(f"[自愈] 自动修复: {动作}")
            结果 = self._执行命令(ssh_cfg, 动作)
            self._记录("自动修复", {"robot": robot_id, "动作": 动作, "结果": str(结果)[:200]})
            self._验证恢复(ssh_cfg, robot_id, 验证列表)

    def _验证恢复(self, ssh_cfg, robot_id, 验证列表=None):
        time.sleep(2)
        for 检查 in (验证列表 or []):
            命令 = 检查["命令"].format(host=ssh_cfg.get("host", ""))
            结果 = self._执行命令(ssh_cfg, 命令)
            self._记录("验证_" + 检查["名称"], {"robot": robot_id, "结果": str(结果)[:200]})

    自愈提示词 = """你是运维诊断专家。根据设备诊断日志判断根因，给出修复命令。
输出 JSON 数组，元素: {"type":"custom","params":{"command":"修复命令"},"priority":1}
命令必须具体可执行，如重启服务、清理缓存、重新加载配置等。
禁止破坏性操作（如格式化、删除系统文件、重启设备）。
无法判断时返回空数组 []"""

    def _LLM诊断(self, 设备类型, 诊断日志):
        """规则无结论时，让 LLM 分析根因并返回修复动作"""
        if not self._llm:
            return None
        # LLM 正在降级 → 跳过
        if hasattr(self._llm, "_降级中") and self._llm._降级中:
            return None
        try:
            prompt = (
                "设备类型: " + 设备类型 + "\n"
                "诊断日志: " + json.dumps(诊断日志, ensure_ascii=False)
            )
            结果 = self._llm._llm决策(
                {
                    "robots": [],
                    "events": [{"type": "诊断", "label": "自愈", "data": {"提示": prompt}}],
                },
                system=self.自愈提示词,
            )
            self._记录("LLM诊断", {"设备": 设备类型, "结论": str(结果)[:200]})
            # _llm决策 返回 RobotOrder 列表，提取 custom 指令的 command
            if 结果:
                for o in 结果:
                    命令 = o.params.get("command", "")
                    if 命令:
                        print(f"[自愈] LLM建议修复: {命令}")
                        # 级别由闸门判定，高危命令仍需人工确认
                        return {"动作": 命令,
                                "级别": "高危" if self._闸门.判断(命令) else "低危"}
            return None
        except Exception as e:
            print(f"[自愈] LLM诊断失败: {e}")
            return None

    def _执行命令(self, ssh_cfg, 命令):
        if not ssh_cfg:
            import subprocess
            try:
                r = subprocess.run(命令, shell=True, capture_output=True, text=True, timeout=10)
                return r.stdout[:500] or r.stderr[:200]
            except Exception as e:
                return str(e)
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ssh_cfg["host"], username=ssh_cfg.get("user", "ysc"),
                        password=ssh_cfg.get("pass", "'"), timeout=5)
            _, stdout, stderr = ssh.exec_command(命令, timeout=10)
            out = stdout.read().decode(errors="replace")
            ssh.close()
            return out[:500]
        except Exception as e:
            return str(e)

    def 获取待确认(self):
        with self._锁:
            return [{"index": i, **p} for i, p in enumerate(self._待确认)]

    def 处理待确认(self, index, action="approve"):
        with self._锁:
            if index < 0 or index >= len(self._待确认):
                return {"ok": False, "msg": "索引无效"}
            item = self._待确认.pop(index)
        if action == "approve":
            print(f"[自愈] 人工确认执行: {item['动作']}")
            ssh_cfg = {"host": "", "user": "ysc", "pass": "'"}
            for d in self._诊断器.values():
                if d.get("ssh", {}).get("host"):
                    ssh_cfg = d["ssh"]
                    break
            结果 = self._执行命令(ssh_cfg, item["动作"])
            self._记录("人工执行", {"robot": item.get("robot"), "动作": item["动作"], "结果": str(结果)[:200]})
        else:
            self._记录("人工拒绝", {"robot": item.get("robot"), "动作": item["动作"]})
        return {"ok": True, "action": action, "item": item}

    def _记录(self, 类型, data):
        entry = {"type": "self_heal", "label": 类型, "data": data, "time": time.time()}
        with self._锁:
            self._历史.append(entry)
            if len(self._历史) > 500:
                self._历史 = self._历史[-250:]
        if self._事件总线:
            try:
                self._事件总线.发布("self_heal", entry)
            except:
                pass
        if self._db:
            try:
                self._db.记录事件(
                    source="self_heal", type=类型, label=类型,
                    robot_id=data.get("robot") if isinstance(data, dict) else None,
                    level=0, priority=0, data=data,
                )
            except Exception as e:
                print(f"[自愈] 记录事件失败: {e}")

    def 获取状态(self):
        return {
            "诊断器": list(self._诊断器.keys()),
            "待确认数": len(self._待确认),
            "历史数": len(self._历史),
            "最近": self._历史[-5:],
        }

    def 获取历史(self, limit=50):
        return self._历史[-limit:]
