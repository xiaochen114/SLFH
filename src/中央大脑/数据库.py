#!/usr/bin/env python3
"""SQLite 持久化层 — 机器人历史、任务日志、巡逻记录、系统配置"""
import os, json, sqlite3, time, threading
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "中央大脑.db")


class 数据库:
    """轻量级 SQLite 封装 — 自动建表、线程安全"""

    def __init__(self, db_path=DB_PATH):
        self._path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._锁 = threading.Lock()
        self._初始化()

    def _连接(self):
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _初始化(self):
        with self._锁:
            conn = self._连接()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS robot_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    robot_id TEXT NOT NULL,
                    robot_type TEXT,
                    battery REAL,
                    mode TEXT,
                    health TEXT,
                    comm_level INTEGER,
                    pos_x REAL,
                    pos_y REAL,
                    timestamp REAL NOT NULL DEFAULT (strftime('%s','now'))
                );
                CREATE INDEX IF NOT EXISTS idx_robot_history_robot ON robot_history(robot_id);
                CREATE INDEX IF NOT EXISTS idx_robot_history_time ON robot_history(timestamp);

                CREATE TABLE IF NOT EXISTS task_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    robot_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    params_json TEXT,
                    priority INTEGER DEFAULT 0,
                    source TEXT DEFAULT 'brain',
                    success INTEGER DEFAULT 1,
                    message TEXT,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                );
                CREATE INDEX IF NOT EXISTS idx_task_robot ON task_log(robot_id);
                CREATE INDEX IF NOT EXISTS idx_task_time ON task_log(created_at);

                CREATE TABLE IF NOT EXISTS patrol_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    point_index INTEGER,
                    point_name TEXT,
                    x REAL,
                    y REAL,
                    status TEXT NOT NULL,
                    started_at REAL,
                    ended_at REAL
                );

                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL DEFAULT (strftime('%s','now'))
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,           -- 来源: yolo / robot / system
                    type TEXT NOT NULL,             -- 事件类型: fire_detected / ...
                    label TEXT,                     -- 标签: 火焰 / 烟雾 / 急停
                    robot_id TEXT,                  -- 相关机器人
                    level INTEGER DEFAULT 0,        -- 严重等级
                    priority INTEGER DEFAULT 0,     -- 紧急度: 0=普通 1=紧急 2=特急
                    data_json TEXT,                 -- 事件数据
                    consumed INTEGER DEFAULT 0,     -- 0=未消费 1=已消费
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                );
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
                CREATE INDEX IF NOT EXISTS idx_events_consumed ON events(consumed);
                CREATE INDEX IF NOT EXISTS idx_events_priority ON events(priority);
                CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
            """)
            conn.commit()
            conn.close()

    # ---- 机器人历史 ----

    def 保存状态快照(self, robot_id, robot_type, battery, mode, health, comm_level, pos=None):
        with self._锁:
            conn = self._连接()
            conn.execute(
                "INSERT INTO robot_history(robot_id, robot_type, battery, mode, health, comm_level, pos_x, pos_y) VALUES (?,?,?,?,?,?,?,?)",
                (robot_id, robot_type, battery, mode, health, comm_level,
                 pos[0] if pos else None, pos[1] if pos else None),
            )
            conn.commit()
            conn.close()

    def 查询状态历史(self, robot_id=None, limit=100):
        with self._锁:
            conn = self._连接()
            if robot_id:
                rows = conn.execute(
                    "SELECT * FROM robot_history WHERE robot_id=? ORDER BY timestamp DESC LIMIT ?",
                    (robot_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM robot_history ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def 清理旧历史(self, keep_hours=72):
        """清理超过 keep_hours 的旧数据"""
        cutoff = time.time() - keep_hours * 3600
        with self._锁:
            conn = self._连接()
            conn.execute("DELETE FROM robot_history WHERE timestamp < ?", (cutoff,))
            conn.execute("DELETE FROM patrol_log WHERE started_at < ?", (cutoff,))
            conn.commit()
            conn.close()

    # ---- 任务日志 ----

    def 记录任务(self, order_id, robot_id, type, params=None, priority=0,
                  source="brain", success=True, message=""):
        with self._锁:
            conn = self._连接()
            conn.execute(
                "INSERT INTO task_log(order_id, robot_id, type, params_json, priority, source, success, message) VALUES (?,?,?,?,?,?,?,?)",
                (order_id, robot_id, type, json.dumps(params or {}),
                 priority, source, 1 if success else 0, message),
            )
            conn.commit()
            conn.close()

    def 查询任务日志(self, robot_id=None, limit=100):
        with self._锁:
            conn = self._连接()
            if robot_id:
                rows = conn.execute(
                    "SELECT * FROM task_log WHERE robot_id=? ORDER BY created_at DESC LIMIT ?",
                    (robot_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM task_log ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    # ---- 巡逻日志 ----

    def 查询巡逻日志(self, limit=100):
        with self._锁:
            conn = self._连接()
            rows = conn.execute(
                "SELECT * FROM patrol_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    # ---- 事件队列（带标签，即取即用）----

    def 记录事件(self, source, type, label="", robot_id=None, level=0, priority=0, data=None):
        """写入事件到数据库（默认未消费）。priority: 0=普通 1=紧急 2=特急"""
        with self._锁:
            conn = self._连接()
            conn.execute(
                "INSERT INTO events(source, type, label, robot_id, level, priority, data_json) VALUES (?,?,?,?,?,?,?)",
                (source, type, label, robot_id, level, priority, json.dumps(data or {}, ensure_ascii=False)),
            )
            conn.commit()
            conn.close()

    def 取未消费事件(self, source=None, type=None, limit=20):
        """取未消费事件（可筛选来源/类型），紧急度高的优先，取出即标记已消费"""
        with self._锁:
            conn = self._连接()
            sql = "SELECT * FROM events WHERE consumed=0"
            params = []
            if source:
                sql += " AND source=?"
                params.append(source)
            if type:
                sql += " AND type=?"
                params.append(type)
            sql += " ORDER BY priority DESC, created_at ASC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            # 标记已消费
            ids = [r["id"] for r in rows]
            if ids:
                conn.execute(
                    f"UPDATE events SET consumed=1 WHERE id IN ({','.join('?' * len(ids))})",
                    ids,
                )
            conn.commit()
            conn.close()
            # 解析 data_json，合并进事件 dict
            result = []
            for r in rows:
                d = dict(r)
                d.update(json.loads(d.pop("data_json", "{}") or "{}"))
                result.append(d)
            return result

    def 查询事件(self, source=None, type=None, limit=100):
        """查询事件历史（不论是否消费）"""
        with self._锁:
            conn = self._连接()
            sql = "SELECT * FROM events"
            conds, params = [], []
            if source:
                conds.append("source=?")
                params.append(source)
            if type:
                conds.append("type=?")
                params.append(type)
            if conds:
                sql += " WHERE " + " AND ".join(conds)
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    # ---- 系统配置 ----

    def 保存配置(self, key, value):
        with self._锁:
            conn = self._连接()
            conn.execute(
                "INSERT OR REPLACE INTO system_config(key, value, updated_at) VALUES (?,?,?)",
                (key, json.dumps(value), time.time()),
            )
            conn.commit()
            conn.close()

    def 获取统计(self):
        """系统概览统计"""
        with self._锁:
            conn = self._连接()
            counts = conn.execute("""
                SELECT 'robot_count' AS k, COUNT(DISTINCT robot_id) AS v FROM robot_history
                UNION ALL SELECT 'task_count', COUNT(*) FROM task_log
                UNION ALL SELECT 'patrol_count', COUNT(*) FROM patrol_log
            """).fetchall()
            # 最近任务
            recent = conn.execute(
                "SELECT * FROM task_log ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            conn.close()
            return {
                "counts": {r["k"]: r["v"] for r in counts},
                "recent_tasks": [dict(r) for r in recent],
            }
