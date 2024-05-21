import argparse

def parse_cli_args():
    parser = argparse.ArgumentParser(description='SRT 로그인 정보 입력')

    parser.add_argument("--user", help="Username", type=str, required=True, metavar="1234567890")
    parser.add_argument("--psw", help="Password", type=str, required=True, metavar="abc1234")

    args = parser.parse_args()

    return args
