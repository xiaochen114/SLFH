#!/usr/bin/env python3
"""
桌面控制端 — 中央大脑的桌面监控面板
通过 API 连接中央大脑，显示机器人状态，下发指令
"""
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="requests")
import os, sys, json, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("需要 tkinter，请安装: python -m install tk")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("需要 requests 库: pip install requests --break-system-packages")
    sys.exit(1)

API_BASE = "http://127.0.0.1:5000"


class 桌面端:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("中央大脑 · 桌面控制端 v1.0")
        self.root.geometry("900x600")
        self.root.configure(bg="#0a1628")
        self.root.minsize(700, 450)

        # 变量
        self.机器人数据 = []
        self._自动刷新 = True

        # 布局
        self._创建顶部()
        self._创建机器人列表()
        self._创建日志框()

        # 启动定时刷新
        self.刷新()

    def _创建顶部(self):
        f = tk.Frame(self.root, bg="#1a2744", height=50)
        f.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(f, text="中央大脑 · 桌面控制端", font=("Microsoft YaHei", 16, "bold"),
                fg="#7aa2e7", bg="#1a2744").pack(side=tk.LEFT, padx=10)

        self.状态标签 = tk.Label(f, text="加载中...", font=("Microsoft YaHei", 10),
                               fg="#888", bg="#1a2744")
        self.状态标签.pack(side=tk.LEFT, padx=20)

        btn = tk.Button(f, text="刷新", command=self.刷新手动,
                       bg="#2B579A", fg="white", font=("Microsoft YaHei", 10))
        btn.pack(side=tk.RIGHT, padx=10)

        self.刷新开关 = tk.Button(f, text="自动刷新:开", command=self.切换自动刷新,
                            bg="#2e7d32", fg="white", font=("Microsoft YaHei", 10))
        self.刷新开关.pack(side=tk.RIGHT, padx=5)

    def _创建机器人列表(self):
        f = tk.Frame(self.root, bg="#0a1628")
        f.pack(fill=tk.BOTH, expand=True, padx=10)

        self.画布 = tk.Canvas(f, bg="#0a1628", highlightthickness=0)
        滚动条 = tk.Scrollbar(f, orient=tk.VERTICAL, command=self.画布.yview)
        self.画布.configure(yscrollcommand=滚动条.set)
        滚动条.pack(side=tk.RIGHT, fill=tk.Y)
        self.画布.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.卡片容器 = tk.Frame(self.画布, bg="#0a1628")
        self.画布.create_window((0, 0), window=self.卡片容器, anchor="nw")
        self.卡片容器.bind("<Configure>", lambda e: self.画布.configure(scrollregion=self.画布.bbox("all")))

    def _创建日志框(self):
        f = tk.Frame(self.root, bg="#0a1628", height=120)
        f.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(f, text="日志", font=("Microsoft YaHei", 10, "bold"),
                fg="#7aa2e7", bg="#0a1628").pack(anchor=tk.W)

        self.日志框 = tk.Text(f, bg="#0d1b2a", fg="#aaa", font=("Consolas", 9),
                            height=5, relief=tk.FLAT)
        self.日志框.pack(fill=tk.X)

    def 刷新(self):
        if self._自动刷新:
            self.刷新手动()
        self.root.after(3000, self.刷新)

    def 刷新手动(self):
        def _跑():
            try:
                r = requests.get(f"{API_BASE}/api/status", timeout=3)
                if r.status_code == 200:
                    self.机器人数据 = r.json()
                    self.root.after(0, self._更新界面)
            except:
                self.root.after(0, lambda: self.状态标签.configure(text="连接失败", fg="#f44336"))
        threading.Thread(target=_跑, daemon=True).start()

    def 切换自动刷新(self):
        self._自动刷新 = not self._自动刷新
        t = "开" if self._自动刷新 else "关"
        c = "#2e7d32" if self._自动刷新 else "#c62828"
        self.刷新开关.configure(text=f"自动刷新:{t}", bg=c)

    def _更新界面(self):
        data = self.机器人数据
        self.状态标签.configure(text=f"总数 {data.get('total',0)} · 在线 {data.get('online',0)}"
                                      f" · 离线 {data.get('total',0)-data.get('online',0)}",
                               fg="#4caf50")

        for w in self.卡片容器.winfo_children():
            w.destroy()

        robots = data.get("robots", [])
        if not robots:
            tk.Label(self.卡片容器, text="暂无注册机器人", font=("Microsoft YaHei", 12),
                    fg="#666", bg="#0a1628").pack(pady=40)
            return

        for r in robots:
            self._创建机器人卡片(r)

        self._日志("刷新成功")

    def _创建机器人卡片(self, r):
        c = tk.Frame(self.卡片容器, bg="#1a2744", relief=tk.RIDGE, bd=1)
        c.pack(fill=tk.X, pady=4, padx=2, ipady=8)

        # 标题行
        h = tk.Frame(c, bg="#1a2744")
        h.pack(fill=tk.X, padx=12, pady=(8, 4))

        tk.Label(h, text=r.get("id", "?"), font=("Microsoft YaHei", 13, "bold"),
                fg="white", bg="#1a2744").pack(side=tk.LEFT)

        t = r.get("type", "")
        ico = "🐕" if t == "dog" else "🛸" if t == "drone" else "?"
        tp = "机器狗" if t == "dog" else "无人机" if t == "drone" else t
        tk.Label(h, text=f"{ico} {tp}", font=("Microsoft YaHei", 10),
                fg="#888", bg="#1a2744").pack(side=tk.LEFT, padx=10)

        # 信息行
        info = tk.Frame(c, bg="#1a2744")
        info.pack(fill=tk.X, padx=12)

        bat = int(r.get("battery", 0) * 100)
        hl = r.get("health", "ok")
        cl = f"L{r.get('comm_level', 3)}"
        md = r.get("mode", "?")

        tk.Label(info, text=f"状态:{hl}  电量:{bat}%  通信:{cl}  模式:{md}",
                font=("Microsoft YaHei", 9), fg="#ccc", bg="#1a2744", anchor=tk.W).pack(side=tk.LEFT, fill=tk.X)

        # 指令按钮
        btns = tk.Frame(c, bg="#1a2744")
        btns.pack(fill=tk.X, padx=12, pady=(4, 0))

        rid = r.get("id", "")
        for cmd, txt in [("stand", "起立"), ("patrol", "巡逻"),
                         ("stop", "停止"), ("alert", "急停")]:
            fg = "#f44336" if cmd == "alert" else "white"
            bg = "#c62828" if cmd == "alert" else "#2a3a5c"
            btn = tk.Button(btns, text=txt, command=lambda i=rid, c=cmd: self._发指令(i, c),
                          bg=bg, fg=fg, font=("Microsoft YaHei", 9), padx=10, pady=2)
            btn.pack(side=tk.LEFT, padx=2)

    def _发指令(self, robot_id, cmd):
        def _跑():
            try:
                r = requests.post(f"{API_BASE}/api/command", json={
                    "robot_id": robot_id, "command": cmd
                }, timeout=3)
                if r.status_code == 200:
                    self._日志(f"{robot_id} → {cmd} 成功")
                else:
                    self._日志(f"{robot_id} → {cmd} 失败")
            except:
                self._日志(f"{robot_id} → {cmd} 连接失败")
        threading.Thread(target=_跑, daemon=True).start()

    def _日志(self, msg):
        try:
            self.日志框.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.日志框.see(tk.END)
        except:
            pass

    def 运行(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = 桌面端()
    app.运行()
