# -*- coding:utf-8 -*-
# @author xupingmao <578749341@qq.com>
# @since 2020/12/06 16:41:11
# @modified 2020/12/06 16:56:01
import sqlite3
import logging

# 配置日志模块
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s|%(levelname)s|%(filename)s:%(lineno)d|%(message)s')

class SqliteTableManager:
    """检查数据库字段，如果不存在就自动创建"""
    def __init__(self, filename, tablename, pkName=None, pkType=None, no_pk=False):
        self.filename = filename
        self.tablename = tablename
        self.db = sqlite3.connect(filename)
        if no_pk:
            # 没有主键，创建一个占位符
            sql = "CREATE TABLE IF NOT EXISTS `%s` (_id int);" % tablename
        elif pkName is None:
            # 只有integer允许AUTOINCREMENT
            sql = "CREATE TABLE IF NOT EXISTS `%s` (id integer primary key autoincrement);" % tablename
        else:
            # sqlite允许主键重复，允许空值
            sql = "CREATE TABLE IF NOT EXISTS `%s` (`%s` %s primary key);" % (tablename, pkName, pkType)
        self.execute(sql)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def execute(self, sql, silent=False):
        cursorobj = self.db.cursor()
        try:
            if not silent:
                print(sql)
            cursorobj.execute(sql)
            kv_result = []
            result = cursorobj.fetchall()
            for single in result:
                resultMap = {}
                for i, desc in enumerate(cursorobj.description):
                    name = desc[0]
                    resultMap[name] = single[i]
                kv_result.append(resultMap)
            self.db.commit()
            return kv_result
        except Exception:
            raise

    def escape(self, strval):
        strval = strval.replace("'", "''")
        return "'%s'" % strval

    def add_column(self, colname, coltype, 
            default_value = None, not_null = False):
        """添加字段，如果已经存在则跳过，名称相同类型不同抛出异常"""
        sql = "ALTER TABLE `%s` ADD COLUMN `%s` %s" % (self.tablename, colname, coltype)

        # MySQL 使用 DESC [表名]
        columns = self.execute("pragma table_info('%s')" % self.tablename, silent=True)
        # print(columns.description)
        # description结构
        for column in columns:
            name = column["name"]
            type = column["type"]
            if name == colname:
                # 已经存在
                return
        if default_value != None:
            if isinstance(default_value, str):
                default_value = self.escape(default_value)
            sql += " DEFAULT %s" % default_value
        if not_null:
            sql += " NOT NULL"
        self.execute(sql)

    def add_index(self, colname, is_unique = False):
        # sqlite的索引和table是一个级别的schema
        if isinstance(colname, list):
            idx_name = "idx_" + self.tablename
            for name in colname:
                idx_name += "_" + name
            colname_str = ",".join(colname)
            sql = "CREATE INDEX IF NOT EXISTS %s ON `%s` (%s)" % (idx_name, self.tablename, colname_str)
        else:
            sql = "CREATE INDEX IF NOT EXISTS idx_%s_%s ON `%s` (`%s`)" % (self.tablename, colname, self.tablename, colname)
        try:
            self.execute(sql)
        except Exception as e:
            logging.error("sql: %s, error: %s", sql, e)

    def drop_index(self, col_name):
        sql = "DROP INDEX idx_%s_%s" % (self.tablename, col_name)
        try:
            self.execute(sql)
        except Exception as e:
            logging.error("sql: %s, error: %s", sql, e)


    def drop_column(self, colname):
        # sql = "ALTER TABLE `%s` DROP COLUMN `%s`" % (self.tablename, colname)
        # sqlite不支持 DROP COLUMN 得使用中间表
        # TODO
        pass

    def generate_migrate_sql(self, dropped_names):
        """生成迁移字段的SQL（本质上是迁移）"""
        columns = self.execute("pragma table_info('%s')" % self.tablename, silent=True)
        new_names = []
        old_names = []
        for column in columns:
            name = column["name"]
            type = column["type"]
            old_names.append(name)
            if name not in dropped_names:
                new_names.append(name)
        # step1 = "ALTER TABLE %s RENAME TO backup_table;" % (self.tablename)
        step2 = "INSERT INTO %s (%s) \nSELECT %s FROM backup_table;" % (
                self.tablename,
                ",".join(new_names),
                ",".join(old_names)
            )
        return step2

    def close(self):
        self.db.close()

TableManager = SqliteTableManager


def init_test_table():
    """测试数据库"""
    path = "./test.db"
    with TableManager(path, "test") as manager:
        manager.add_column("id1", "integer", 0)
        manager.add_column("int_value", "int", 0)
        manager.add_column("float_value", "float")
        manager.add_column("text_value", "text", "")
        manager.add_column("name", "text", "test")
        manager.add_column("check", "text", "aaa'bbb")
        manager.add_index("check")

