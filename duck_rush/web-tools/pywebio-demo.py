from pywebio.input import input, FLOAT, input_group
from pywebio.output import put_text

def bmi_app():
    info = input_group("User info",[
        input("身高(cm)：", type=FLOAT, name="height"),
        input("体重(kg)：", type=FLOAT, name="width")
    ])
    h = info["height"]
    w = info["width"]
    bmi = w/(h/100)**2
    put_text(f"你的BMI：{bmi:.1f}")

if __name__ == "__main__":
    from pywebio import start_server
    start_server(bmi_app, host="127.0.0.1", port=8080)  # 浏览器访问http://localhost:8080
