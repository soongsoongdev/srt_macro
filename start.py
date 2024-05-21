
from srt_reservation.util import parse_cli_args
from srt_reservation.main import SRT

if __name__ == "__main__":
    args = parse_cli_args()
    srt = SRT(args.user, args.psw)
    srt.login()
    # 이후의 동작을 추가할 수 있음 (예: 페이지 이동, 데이터 추출 등)
    srt.close()