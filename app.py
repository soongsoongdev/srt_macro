from flask import Flask, render_template, request, redirect, url_for, jsonify
from srt_reservation.main import SRT
import threading

app = Flask(__name__)

station_list = ["수서", "동탄", "평택지제", "천안아산", "오송", "대전", "김천(구미)", "동대구",
                "신경주", "울산(통도사)", "부산", "공주", "익산", "정읍", "광주송정", "나주", "목포"]

srt_instance = None
srt_thread = None
shutdown_flag = False


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        dpt = request.form["dpt"]
        arr = request.form["arr"]
        dpt_dt = request.form['dpt_dt'].replace("-", "")  # 날짜 형식 변경
        dpt_tm = str(request.form["dpt_tm"])
        num_trains_to_check = int(request.form['num_trains_to_check'])

        global srt_instance, srt_thread, shutdown_flag
        shutdown_flag = False

        def run_srt():
            global srt_instance, shutdown_flag
            srt_instance = SRT('회원번호', '비밀번호', dpt, arr, dpt_dt, dpt_tm, num_trains_to_check, True)
            srt_instance.login()
            srt_instance.go_search()
            srt_instance.check_result()
            srt_instance.close()

        srt_thread = threading.Thread(target=run_srt)
        srt_thread.start()
        return render_template("index.html", station_list=station_list, success_message="로그인 및 예약 처리 완료!")

    return render_template('index.html', station_list=station_list)


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
