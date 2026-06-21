"""
Textual Demo — 组件展示与功能演示

入口为功能列表菜单，点击可进入各演示页面。
每个演示页面按 Esc 返回菜单。
"""

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Label, Static, Button, Input,
    ListView, ListItem, Checkbox, RadioSet, RadioButton,
    Switch, Select, ProgressBar,
    TabbedContent, TabPane,
)
from textual.containers import Vertical, Horizontal, ScrollableContainer

# ============================================================
# 工具函数
# ============================================================

BMI_CATEGORIES = [
    (18.5, "偏瘦"),
    (24.0, "正常"),
    (28.0, "偏胖"),
    (float("inf"), "肥胖"),
]


def calc_bmi(weight: float, height_cm: float) -> float:
    return weight / ((height_cm / 100) ** 2)


def bmi_category(bmi: float) -> str:
    for threshold, label in BMI_CATEGORIES:
        if bmi < threshold:
            return label
    return "肥胖"


# ============================================================
# 1. 主菜单
# ============================================================

class MenuScreen(Screen):
    TITLE = "Textual Demo"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="menu"):
            yield Label("Textual Demo\n选择一个功能", id="menu-title")
            yield ListView(
                ListItem(Label("BMI 计算器")),
                ListItem(Label("组件总览")),
                ListItem(Label("计数器")),
                ListItem(Label("待办列表")),
                ListItem(Label("退出"), id="menu-exit"),
            )
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        screens = [BmiScreen, WidgetsScreen, CounterScreen, TodoScreen]
        if event.index == 4:
            self.app.exit()
        elif 0 <= event.index < len(screens):
            self.app.push_screen(screens[event.index]())


# ============================================================
# 2. BMI 计算器
# ============================================================

class BmiScreen(Screen):
    TITLE = "BMI 计算器"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="bmi-form"):
            yield Label("BMI 计算器", id="bmi-title")
            yield Input(placeholder="身高（厘米）", id="bmi-height")
            yield Input(placeholder="体重（公斤）", id="bmi-weight")
            with Horizontal():
                yield Button("计算", variant="primary", id="bmi-calc")
                yield Button("返回菜单", id="bmi-back")
            yield Static("", id="bmi-result")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "bmi-back":
            self.app.pop_screen()
            return
        if event.button.id != "bmi-calc":
            return
        height = self.query_one("#bmi-height", Input).value
        weight = self.query_one("#bmi-weight", Input).value
        result = self.query_one("#bmi-result", Static)
        try:
            h = float(height)
            w = float(weight)
        except (ValueError, TypeError):
            result.update("请输入有效的数字")
            return
        if h <= 0 or w <= 0:
            result.update("身高和体重必须大于 0")
            return
        bmi = calc_bmi(w, h)
        cat = bmi_category(bmi)
        result.update(f"BMI: {bmi:.1f}\n分类: {cat}")


# ============================================================
# 3. 组件总览
# ============================================================

class WidgetsScreen(Screen):
    TITLE = "组件总览"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="widgets-scroll"):
            yield Label("Button 按钮", classes="section-title")
            with Horizontal(id="btn-row"):
                yield Button("Primary", variant="primary")
                yield Button("Success", variant="success")
                yield Button("Warning", variant="warning")
                yield Button("Error", variant="error")

            yield Label("Input 输入框", classes="section-title")
            yield Input(placeholder="在此输入文字...")

            yield Label("Checkbox 复选框", classes="section-title")
            yield Checkbox("我已阅读并同意", id="w-checkbox")
            yield Static("", id="w-checkbox-status")

            yield Label("RadioSet 单选组", classes="section-title")
            with RadioSet(id="w-radio"):
                yield RadioButton("选项 A")
                yield RadioButton("选项 B")
                yield RadioButton("选项 C")
            yield Static("选中: 选项 A", id="w-radio-status")

            yield Label("Switch 开关", classes="section-title")
            yield Switch(id="w-switch")
            yield Static("开关: 关", id="w-switch-status")

            yield Label("Select 下拉选择", classes="section-title")
            yield Select(
                [("苹果", "apple"), ("香蕉", "banana"), ("橘子", "orange")],
                id="w-select",
            )
            yield Static("选择: 苹果", id="w-select-status")

            yield Label("ProgressBar 进度条", classes="section-title")
            yield ProgressBar(total=100, id="w-progress")
            yield Static("进度: 0%", id="w-progress-status")

            yield Label("TabbedContent 标签页", classes="section-title")
            with TabbedContent(initial="tab-a"):
                with TabPane("标签 A", id="tab-a"):
                    yield Label("这是标签 A 的内容")
                    yield Button("标签 A 按钮", variant="primary")
                with TabPane("标签 B", id="tab-b"):
                    yield Label("这是标签 B 的内容")
                    with Horizontal():
                        yield Checkbox("B 选项 1")
                        yield Checkbox("B 选项 2")
                with TabPane("标签 C", id="tab-c"):
                    yield Label("这是标签 C 的内容")
                    yield Input(placeholder="在标签 C 中输入...", id="tab-c-input")
                    yield Static("你输入的内容会显示在这里", id="tab-c-output")

            yield Button("返回菜单", id="w-back")

        yield Footer()

    def on_mount(self) -> None:
        self._progress = 0
        self._timer = self.set_interval(0.1, self._advance_progress)

    def on_unmount(self) -> None:
        if hasattr(self, "_timer"):
            self._timer.stop()

    def _advance_progress(self) -> None:
        self._progress = (self._progress + 1) % 101
        self.query_one("#w-progress", ProgressBar).progress = self._progress
        self.query_one("#w-progress-status", Static).update(
            f"进度: {self._progress}%"
        )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.query_one("#w-checkbox-status", Static).update(
            "已勾选" if event.value else "未勾选"
        )

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.query_one("#w-radio-status", Static).update(
            f"选中: {event.pressed.label.plain}"
        )

    def on_switch_changed(self, event: Switch.Changed) -> None:
        self.query_one("#w-switch-status", Static).update(
            "开关: 开" if event.value else "开关: 关"
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        labels = {"apple": "苹果", "banana": "香蕉", "orange": "橘子"}
        self.query_one("#w-select-status", Static).update(
            f"选择: {labels.get(event.value, str(event.value))}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "w-back":
            self.app.pop_screen()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "tab-c-input":
            self.query_one("#tab-c-output", Static).update(
                f"你输入的内容: {event.value}"
            )


# ============================================================
# 4. 计数器
# ============================================================

class CounterScreen(Screen):
    TITLE = "计数器"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="counter-app"):
            yield Label("0", id="counter-value")
            yield ProgressBar(total=100, id="counter-bar")
            with Horizontal(id="counter-btns"):
                yield Button("-10", id="c-dec10")
                yield Button("-1", id="c-dec1")
                yield Button("重置", id="c-reset")
                yield Button("+1", id="c-inc1")
                yield Button("+10", id="c-inc10")
            yield Button("返回菜单", id="c-back")
        yield Footer()

    def on_mount(self) -> None:
        self._count = 0
        self._update_display()

    def _update_display(self) -> None:
        self.query_one("#counter-value", Label).update(str(self._count))
        self.query_one("#counter-bar", ProgressBar).progress = max(
            0, min(100, self._count)
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "c-back":
            self.app.pop_screen()
        elif bid == "c-inc1":
            self._count += 1
        elif bid == "c-dec1":
            self._count -= 1
        elif bid == "c-inc10":
            self._count += 10
        elif bid == "c-dec10":
            self._count -= 10
        elif bid == "c-reset":
            self._count = 0
        self._update_display()


# ============================================================
# 5. 待办列表
# ============================================================

class TodoScreen(Screen):
    TITLE = "待办列表"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="todo-app"):
            with Horizontal(id="todo-input-row"):
                yield Input(placeholder="输入待办事项...", id="todo-input")
                yield Button("添加", variant="primary", id="todo-add")
            yield ScrollableContainer(id="todo-list")
            with Horizontal(id="todo-actions"):
                yield Button("删除已完成", id="todo-clear")
                yield Button("返回菜单", id="todo-back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "todo-add":
            inp = self.query_one("#todo-input", Input)
            text = inp.value.strip()
            if text:
                inp.value = ""
                container = self.query_one("#todo-list")
                idx = len(list(container.children))
                item = Horizontal(
                    Checkbox(text, id=f"tcb{idx}"),
                    Button("✕", id=f"trm{idx}"),
                    id=f"tit{idx}",
                )
                container.mount(item)
                item.scroll_visible()
        elif bid == "todo-clear":
            container = self.query_one("#todo-list")
            for child in list(container.children):
                cb = child.query_one(Checkbox)
                if cb.value:
                    child.remove()
        elif bid == "todo-back":
            self.app.pop_screen()
        elif bid and bid.startswith("trm"):
            event.button.parent.remove()


# ============================================================
# 主应用
# ============================================================

APP_CSS = """
Screen {
    background: $surface;
}

#menu-title {
    content-align: center middle;
    text-style: bold;
    height: 3;
    margin-top: 2;
}

ListView {
    margin: 1 4;
    height: auto;
    max-height: 12;
}

.section-title {
    margin: 1 0 0 2;
    text-style: bold;
    color: $accent;
}

#btn-row {
    align: center middle;
    margin: 1 2;
}

#btn-row Button {
    margin: 0 1;
}

#bmi-form {
    align: center top;
    margin: 2 4;
}

#bmi-title {
    text-style: bold;
    content-align: center middle;
    height: 3;
}

#bmi-result {
    margin: 1 0;
    text-style: bold;
}

#counter-app {
    align: center top;
    margin: 2 4;
}

#counter-value {
    content-align: center middle;
    text-style: bold;
    height: 5;
    color: $success;
}

#counter-bar {
    margin: 1 4;
}

#counter-btns {
    align: center middle;
    margin: 1 0;
}

#counter-btns Button {
    margin: 0 1;
}

#todo-app {
    margin: 1 2;
}

#todo-input-row {
    margin: 1 0;
}

#todo-input {
    width: 1fr;
}

#todo-list {
    height: 1fr;
    border: solid $primary;
    min-height: 6;
}

#todo-list Horizontal {
    height: 3;
}

#todo-list Checkbox {
    width: 1fr;
}

#todo-list Button {
    width: 5;
}

#todo-actions {
    margin: 1 0;
}

#w-back {
    margin: 2 2;
}

TabbedContent {
    margin: 0 2;
    height: 12;
}
"""


class TextualDemo(App):
    CSS = APP_CSS
    TITLE = "Textual Demo"

    def on_mount(self) -> None:
        self.push_screen(MenuScreen())


if __name__ == "__main__":
    app = TextualDemo()
    app.run()
