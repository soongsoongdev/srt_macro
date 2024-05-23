import warnings
from random import randint

from selenium import webdriver
from selenium.common import StaleElementReferenceException, ElementClickInterceptedException, NoSuchElementException, \
    UnexpectedAlertPresentException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.select import Select

# 경고 무시 (임시)
warnings.filterwarnings("ignore", category=UserWarning)


class SRT:
    def __init__(self, username, password, dpt_stn, arr_stn, dpt_dt, dpt_tm, want_reserve, driver_path='/Users/macbook/PycharmProjects/SRT/chromedriver', selected_trains=None):
        self.username = username
        self.password = password
        self.dpt_stn = dpt_stn
        self.arr_stn = arr_stn
        self.dpt_dt = dpt_dt
        self.dpt_tm = dpt_tm
        self.driver_path = driver_path
        self.want_reserve = want_reserve
        self.selected_trains = selected_trains if selected_trains is not None else []
        self.driver = None
        self.is_booked = False  # 예약 완료 되었는지 확인용
        self.cnt_refresh = 0  # 새로고침 회수 기록
        self.stop_flag = False  # 종료 신호

    def setup_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # 브라우저를 표시하지 않고 실행하려면 이 줄을 주석 해제
        service = Service(self.driver_path)
        self.driver = webdriver.Chrome(service=service, options=options)

    def login(self):
        self.setup_driver()
        self.driver.get('https://etk.srail.kr/cmc/01/selectLoginForm.do')

        # 아이디 입력 필드 찾기 및 입력
        id_field = self.driver.find_element(By.ID, 'srchDvNm01')
        id_field.send_keys(self.username)

        # 비밀번호 입력 필드 찾기 및 입력
        password_field = self.driver.find_element(By.ID, 'hmpgPwdCphd01')
        password_field.send_keys(self.password)

        # 로그인 버튼 클릭 (XPATH 사용)
        login_button = self.driver.find_element(By.XPATH,
                                                '//*[@id="login-form"]/fieldset/div[1]/div[1]/div[2]/div/div[2]/input')
        login_button.click()

        # 로그인 완료 대기 (필요에 따라 조정)
        time.sleep(5)

    def go_search(self):
        print(self.dpt_dt, self.arr_stn, self.dpt_tm)
        # 기차 조회 페이지로 이동
        self.driver.get('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do')
        self.driver.implicitly_wait(5)

        # 출발지 입력
        elm_dpt_stn = self.driver.find_element(By.ID, 'dptRsStnCdNm')
        elm_dpt_stn.clear()
        elm_dpt_stn.send_keys(self.dpt_stn)

        # 도착지 입력
        elm_arr_stn = self.driver.find_element(By.ID, 'arvRsStnCdNm')
        elm_arr_stn.clear()
        elm_arr_stn.send_keys(self.arr_stn)
        # 출발 날짜 입력
        print(f"출발 날짜: {self.dpt_dt}")
        elm_dpt_dt = self.driver.find_element(By.ID, "dptDt")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_dt)
        Select(elm_dpt_dt).select_by_value(self.dpt_dt)

        # 출발 시간 입력
        print(f"출발 시간: {self.dpt_tm}")
        elm_dpt_tm = self.driver.find_element(By.ID, "dptTm")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_tm)
        Select(elm_dpt_tm).select_by_visible_text(self.dpt_tm)

        print("기차를 조회합니다")
        print(
            f"출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n날짜:{self.dpt_dt}, 시간: {self.dpt_tm}시 이후 예약")
        print(f"예약 대기 사용: {self.want_reserve}")

        self.driver.find_element(By.XPATH, "//input[@value='조회하기']").click()
        self.driver.implicitly_wait(5)
        time.sleep(1)

    def book_ticket(self, standard_seat, i):
        # standard_seat는 일반석 검색 결과 텍스트

        if "예약하기" in standard_seat:
            print("예약 가능 클릭")

            # Error handling in case that click does not work
            try:
                self.driver.find_element(By.CSS_SELECTOR,
                                         f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7) > a").click()
            except ElementClickInterceptedException as err:
                print(err)
                self.driver.find_element(By.CSS_SELECTOR,
                                         f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7) > a").send_keys(
                    Keys.ENTER)
            finally:
                self.driver.implicitly_wait(3)
            try:
                # 예약이 성공하면
                if self.driver.find_elements(By.ID, 'isFalseGotoMain'):
                    self.is_booked = True
                    print("예약 성공")
                    return self.driver
                else:
                    print("잔여석 없음. 다시 검색")
                    self.driver.back()  # 뒤로가기
                    self.driver.implicitly_wait(5)
            except UnexpectedAlertPresentException as err:
                print(err)
                print("선택하신 열차는 SRT 2개 편성을 연결하여 운행하는 열차로서, 반드시 열차번호와 해당호차를 확인하시고 승차하시기 바랍니다.")


    def refresh_result(self):
        if self.stop_flag:
            return
        submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
        self.driver.execute_script("arguments[0].click();", submit)
        self.cnt_refresh += 1
        print(f"새로고침 {self.cnt_refresh}회")
        self.driver.implicitly_wait(10)
        time.sleep(0.5)

    def reserve_ticket(self, reservation, i):
        if "신청하기" in reservation:
            print("예약 대기 완료")
            self.driver.find_element(By.CSS_SELECTOR,
                                     f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8) > a").click()
            self.is_booked = True
            return self.is_booked

    def stop(self):
        self.stop_flag = True
        self.close()

    def close(self):
        if self.driver:
            self.driver.quit()

    def get_train_list(self):
        trains = []
        for i in range(1, 11):  # 임시로 10개의 기차를 가져옴
            try:
                info = self.driver.find_element(By.CSS_SELECTOR,
                                                f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i})").text
                trains.append({"index": i, "info": info})
            except NoSuchElementException:
                break
        return trains


    def check_selected_trains(self):
        while not self.stop_flag:
            for i in self.selected_trains:
                if self.stop_flag:
                    break
                try:
                    standard_seat = self.driver.find_element(By.CSS_SELECTOR,
                                                             f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7)").text
                    reservation = self.driver.find_element(By.CSS_SELECTOR,
                                                           f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8)").text
                except StaleElementReferenceException:
                    standard_seat = "매진"
                    reservation = "매진"
                except NoSuchElementException:
                    standard_seat = "매진"
                    reservation = "매진"

                if self.book_ticket(standard_seat, i):
                    return self.driver

                if self.want_reserve:
                    self.reserve_ticket(reservation, i)

            if self.is_booked:
                return self.driver

            else:
                time.sleep(randint(2, 4))
                self.refresh_result()
