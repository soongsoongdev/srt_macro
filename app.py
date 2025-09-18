from flask import Flask, render_template, request, redirect, url_for, jsonify
from srt_reservation.main import SRT
import threading

app = Flask(__name__)

station_list = ["수서", "동탄", "평택지제", "천안아산", "오송", "대전", "김천(구미)", "동대구", "신경주", "울산(통도사)", "부산", "공주", "익산", "정읍", "광주송정", "나주", "목포", "창원"]

srt_instance = None
srt_thread = None
shutdown_flag = False

# 전역 변수 선언
dpt = ""
arr = ""
dpt_dt = ""
dpt_tm = ""

@app.route("/", methods=["GET", "POST"])
def index():
    global dpt, arr, dpt_dt, dpt_tm  # 전역 변수 사용 선언
    if request.method == "POST":
        dpt = request.form["dpt"]
        arr = request.form["arr"]
        dpt_dt = request.form['dpt_dt'].replace("-", "")  # 날짜 형식 변경
        dpt_tm = str(request.form["dpt_tm"])
        srt = SRT('', '!', dpt, arr, dpt_dt, dpt_tm, True)
        srt.login()
        srt.go_search()
        train_list = srt.get_train_list()
        srt.close()

        return render_template('index.html', station_list=station_list, train_list=train_list)
    return render_template('index.html', station_list=station_list)


@app.route("/select_trains", methods=["POST"])
def select_trains():
    selected_trains = request.form.getlist("selected_trains")
    selected_trains = list(map(int, selected_trains))

    global srt_instance, srt_thread, dpt, arr, dpt_dt, dpt_tm  # 전역 변수 사용 선언

    def run_srt():
        global srt_instance
        print(dpt, dpt_dt, arr, dpt_dt, dpt_tm)
        srt_instance = SRT('2499463546', 'nanacorn99!', dpt, arr, dpt_dt, dpt_tm, len(selected_trains), '/Users/gaehyun/Documents/project/srt_macro/chromedriver',
                           selected_trains=selected_trains)
        srt_instance.login()
        srt_instance.go_search()

        print("조회된 열차:")
        for t in srt_instance.get_train_list():
            print(t)

        srt_instance.check_selected_trains()

    srt_thread = threading.Thread(target=run_srt)
    srt_thread.start()
    return redirect(url_for("index"))  # 예약 시도 후 메인 페이지로 리디렉션


@app.route("/shutdown", methods=['POST'])
def shutdown():
    global srt_instance, srt_thread, shutdown_flag
    if srt_instance:
        srt_instance.stop()
        if srt_thread and srt_thread.is_alive():
            srt_thread.join()
        shutdown_flag = True
    return jsonify({"status": "stopped"})


@app.route("/status")
def status():
    global srt_instance
    return jsonify({"cnt_refresh": srt_instance.cnt_refresh if srt_instance else 0, "shutdown_flag": shutdown_flag})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)
