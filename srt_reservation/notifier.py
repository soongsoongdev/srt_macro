# srt_reservation/notifier.py
import os
import json
import time
import subprocess
import urllib.request

# (옵션) Slack/Discord 웹훅 URL을 환경변수로 넣어두면 동시에 푸시도 보냅니다.
# 예) export SRT_WEBHOOK="https://hooks.slack.com/services/xxx/yyy/zzz"
WEBHOOK_URL = os.environ.get("SRT_WEBHOOK")

def notify(msg: str):
    """
    예약 '성공' 시점에서만 호출하세요.
    - macOS 알림센터 배너
    - 큰 알림음 2~3회 반복
    - (옵션) 웹훅 전송
    """
    print(f"[NOTIFY] {msg}")
    _song_notify()
    _sound_notify()
    _webhook_notify(msg)

def _run(cmd: list[str]) -> int:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            # 실패 로그 (디버깅용)
            err = p.stderr.decode(errors="ignore")
            if err:
                print(f"[NOTIFY:cmd fail] {cmd} -> {p.returncode}\n{err}")
        return p.returncode
    except Exception as e:
        print(f"[NOTIFY:exec error] {cmd} -> {e}")
        return -1

def _song_notify():
    """
    사용자 지정 음악 파일을 2~3회 크게 재생
    macOS: afplay 사용
    """
    # 알림용 음악 파일 (예: project/srt_macro/alert.mp3)
    music_path = "/Users/gaehyun/Documents/project/srt_macro/song.mp3"

    if os.path.exists(music_path):
        for _ in range(3):  # 3회 반복
            _run(["/usr/bin/afplay", music_path])
            time.sleep(0.5)
    else:
        print(f"[NOTIFY] 음악 파일 없음: {music_path}")


def _macos_notify(msg: str):
    # 알림센터 배너 (집중 모드/권한의 영향을 받을 수 있음)
    _run(["/usr/bin/osascript", "-e",
          f'display notification "{msg}" with title "SRT 매크로"'])

def _sound_notify():
    """
    소리 재생(큼직하게)
    1) /usr/bin/afplay 로 시스템 효과음을 3회 반복
    2) osascript 'beep' 3회
    3) say 로 2회 음성 안내
    """
    sound_candidates = [
        "/System/Library/Sounds/Hero.aiff",       # 큼직한 효과음
        "/System/Library/Sounds/Submarine.aiff",
        "/System/Library/Sounds/Glass.aiff",
        "/System/Library/Sounds/Funk.aiff",
    ]

    # 1) afplay 3회 반복
    for path in sound_candidates:
        if os.path.exists(path):
            ok = False
            for _ in range(3):
                rc = _run(["/usr/bin/afplay", path])
                ok = (rc == 0) or ok
            if ok:
                return

    # 2) beep 3회
    for _ in range(3):
        _run(["/usr/bin/osascript", "-e", "beep 1"])
        time.sleep(0.4)

    # 3) 음성합성 2회
    for _ in range(2):
        _run(["/usr/bin/say", "S. R. T. 예약 성공"])
        time.sleep(0.2)

def _webhook_notify(msg: str):
    if not WEBHOOK_URL:
        return
    try:
        data = json.dumps({"text": msg}).encode("utf-8")
        req = urllib.request.Request(
            WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=3).read()
    except Exception as e:
        print(f"[NOTIFY:webhook fail] {e}")
