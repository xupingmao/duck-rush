# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2023/02/05 13:48:09
# @modified 2023/02/05 13:59:45

import os
import sys
import sqlite3
import argparse
import traceback


def print_table(rows, headers):
    if not rows:
        print("(empty)")
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))
    fmt = "  ".join("{:<%d}" % w for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*[str(v) for v in row]))
    print("\n(%d rows)" % len(rows))


def print_rows_line(rows, headers):
    if not rows:
        print("(empty)")
        return
    for idx, row in enumerate(rows):
        print("-%d-" % (idx + 1))
        for i, val in enumerate(row):
            print("  %s = %s" % (headers[i], val))
        print()
    print("(%d rows)" % len(rows))


def print_help():
    print("""
.quit     退出 shell
.q        退出 shell
.exit     退出 shell
.tables   列出所有表
.schema   [table] 显示建表语句
.databases 显示数据库列表
.headers  on|off 切换是否显示列名
.mode     column|line 切换输出模式
.help     显示帮助信息
""")


class SqliteShell:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.show_headers = True
        self.mode = "column"
        self._init_dot_cmd_map()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def list_tables(self):
        rows, _ = self.query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if self.mode == "column":
            print_table(rows, ["tables"])
        else:
            print_rows_line(rows, ["tables"])

    def show_schema(self, table_name=None):
        if table_name:
            rows, _ = self.query(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
        else:
            rows, _ = self.query(
                "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
            )
        for row in rows:
            print(row[0])
            print()

    def show_databases(self):
        print(self.db_path)

    def query(self, sql, params=None):
        assert self.conn != None
        cursor = self.conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            if sql.strip().upper().startswith("SELECT") or \
               sql.strip().upper().startswith("PRAGMA") or \
               cursor.description:
                rows = cursor.fetchall()
                headers = [desc[0] for desc in cursor.description] if cursor.description else []
                return rows, headers
            else:
                self.conn.commit()
                print("受影响行数: %d" % cursor.rowcount)
                return [], []
        finally:
            cursor.close()

    def execute_sql(self, sql):
        try:
            rows, headers = self.query(sql)
            if not headers:
                return
            if self.show_headers:
                if self.mode == "column":
                    print_table(rows, headers)
                else:
                    print_rows_line(rows, headers)
            else:
                if self.mode == "column":
                    print_table(rows, [""] * len(headers))
                else:
                    print_rows_line(rows, [""] * len(headers))
        except Exception as e:
            print("Error: %s" % e)

    _DOT_EXIT = {"quit", "q", "exit"}

    def _init_dot_cmd_map(self):
        self._dot_cmd_map = {
            "tables": lambda a: self.list_tables(),
            "schema": lambda a: self.show_schema(a),
            "databases": lambda a: self.show_databases(),
            "headers": self._set_headers,
            "mode": self._set_mode,
            "help": lambda a: print_help(),
        }

    def _set_headers(self, arg):
        self.show_headers = not (arg and arg.lower() == "off")

    def _set_mode(self, arg):
        self.mode = "line" if arg and arg.lower() == "line" else "column"

    def exec_dot_command(self, line):
        parts = line[1:].strip().split()
        if not parts:
            return True
        cmd = parts[0].lower()
        arg = " ".join(parts[1:]) if len(parts) > 1 else None
        if cmd in self._DOT_EXIT:
            return False
        handler = self._dot_cmd_map.get(cmd)
        if handler:
            handler(arg)
        else:
            print("未知命令: %s，输入 .help 查看帮助" % cmd)
        return True

    def run_interactive(self):
        try:
            import readline
        except ImportError:
            pass
        print("SQLite shell, 输入 .help 查看帮助")
        while True:
            try:
                line = input("sqlite> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.startswith("."):
                if not self.exec_dot_command(line):
                    break
            else:
                self.execute_sql(line)

    def run_one_shot(self, sql):
        self.execute_sql(sql)


def main():
    parser = argparse.ArgumentParser(description="SQLite 命令行工具")
    parser.add_argument("database", help="数据库文件路径")
    parser.add_argument("sql", nargs="?", default=None, help="要执行的 SQL 语句（可选，不指定则进入交互模式）")
    parser.add_argument("-c", "--create", action="store_true", help="如果数据库文件不存在，自动创建")
    args = parser.parse_args()

    if not os.path.exists(args.database):
        if args.create:
            print("创建数据库文件: %s" % args.database)
        else:
            print("数据库文件不存在: %s" % args.database)
            sys.exit(1)

    shell = SqliteShell(args.database)
    try:
        if args.sql:
            shell.run_one_shot(args.sql)
        else:
            shell.run_interactive()
    finally:
        shell.close()


if __name__ == "__main__":
    main()
