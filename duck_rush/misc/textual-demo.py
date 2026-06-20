from textual.app import App, ComposeResult
from textual.widgets import Input, Button, Label, Static
from textual.containers import Vertical, Horizontal


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


class BmiApp(App):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("BMI 计算器", id="title")
            yield Input(placeholder="身高（厘米）", id="height")
            yield Input(placeholder="体重（公斤）", id="weight")
            with Horizontal():
                yield Button("计算", variant="primary", id="calc")
                yield Button("退出", id="exit")
            yield Static("", id="result")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "exit":
            self.exit()
            return
        if event.button.id != "calc":
            return
        height = self.query_one("#height", Input).value
        weight = self.query_one("#weight", Input).value
        result = self.query_one("#result", Static)

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
        category = bmi_category(bmi)
        result.update("BMI: %.1f\n分类: %s" % (bmi, category))


if __name__ == "__main__":
    app = BmiApp()
    app.run()
