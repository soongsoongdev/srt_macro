import warnings
import time
import re
from typing import Optional
from random import randint
from srt_reservation.notifier import notify

from selenium import webdriver
from selenium.common import (
    StaleElementReferenceException,
    ElementClickInterceptedException,
    NoSuchElementException,
    UnexpectedAlertPresentException,
)
from selenium.webdriver import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 경고 무시 (임시)
warnings.filterwarnings("ignore", category=UserWarning)


class SRT:
    def __init__(
        self,
        username,
        password,
        dpt_stn,
        arr_stn,
        dpt_dt,
        dpt_tm,
        want_reserve,
        driver_path="/Users/gaehyun/Documents/project/srt_macro/chromedriver",
        selected_trains=None,
    ):
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
        self.is_booked = False
        self.cnt_refresh = 0
        self.stop_flag = False

    # ---------- 드라이버 ----------
    def setup_driver(self):
        options = webdriver.ChromeOptions()
        # 디버깅 시 headless를 끄는 것이 편리합니다.
        # options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--remote-allow-origins=*")

        service = Service(self.driver_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(0)

    # ---------- 로그인 ----------
    def login(self, method="회원번호"):
        self.setup_driver()
        self.driver.get("https://etk.srail.kr/cmc/01/selectLoginForm.do")

        # 대기열 해제까지 대기
        wait_until_queue_clears(self.driver, max_wait_sec=3600, poll=3)

        wait = WebDriverWait(self.driver, 15)
        # 그 다음 성공 신호 대기
        wait.until(EC.any_of(
            EC.url_contains("selectScheduleList"),
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(.,'마이페이지') or contains(.,'승차권') or contains(.,'조회')]"))
        ))
        self._try_close_simple_banners()

        # 로그인 방식 매핑
        method_map = {
            "회원번호": ("srchDvCd1", "srchDvNm01", "hmpgPwdCphd01"),
            "이메일": ("srchDvCd2", "srchDvNm02", "hmpgPwdCphd02"),
            "휴대전화번호": ("srchDvCd3", "srchDvNm03", "hmpgPwdCphd03"),
        }
        if method not in method_map:
            method = "회원번호"

        radio_id, id_input_id, pwd_input_id = method_map[method]

        # 로그인 방식 선택
        try:
            radio_el = wait.until(EC.element_to_be_clickable((By.ID, radio_id)))
            radio_el.click()
        except Exception:
            pass

        # 입력 필드
        id_input = wait.until(EC.element_to_be_clickable((By.ID, id_input_id)))
        pwd_input = wait.until(EC.element_to_be_clickable((By.ID, pwd_input_id)))

        id_input.clear()
        id_input.send_keys(self.username)

        pwd_input.clear()
        pwd_input.send_keys(self.password)

        # 로그인 버튼 클릭
        submit_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input.submit.loginSubmit[value='확인']"))
        )
        self.driver.execute_script("arguments[0].click();", submit_btn)

        # 로그인 성공 신호 대기
        wait.until(
            EC.any_of(
                EC.url_contains("selectScheduleList"),
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//*[contains(.,'마이페이지') or contains(.,'승차권') or contains(.,'조회')]",
                    )
                ),
            )
        )

    def book_special_ticket(self, special_seat, i):
        """
        특실(6열)에서 '예약하기' 또는 '좌석선택'이면 클릭 시도
        """
        label = (special_seat or "").strip()
        if ("예약하기" not in label) and ("좌석선택" not in label):
            return None

        print(f"[{i}] 특실 '{label}' 클릭")
        wait = WebDriverWait(self.driver, 10)

        # 해당 행의 6번째 셀 안에서 텍스트가 정확히 일치하는 버튼만 클릭
        xp = (
            f"(//table/tbody/tr)[{i}]"
            f"/td[6]//*[self::a or self::button][normalize-space()='예약하기' or normalize-space()='좌석선택']"
        )
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
        try:
            self.driver.execute_script("arguments[0].click();", btn)
        except ElementClickInterceptedException:
            try:
                btn.send_keys(Keys.ENTER)
            except Exception:
                pass

        # 성공 신호 대기
        try:
            WebDriverWait(self.driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "isFalseGotoMain")),
                    EC.url_contains("selectReservationComplete"),
                )
            )
            self.is_booked = True
            print("예약 성공 ✅(특실)")
            notify(f"[{i}] 특실 예약 성공 ✅")  # ✅ 알림 추가
            return self.driver
        except Exception:
            print("잔여석 없음/전환 실패 → 뒤로가기(특실)")
            self.driver.back()
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#result-form table tbody"))
            )
            return None


    def _try_close_simple_banners(self):
        """공지/팝업 닫기"""
        for xp in [
            "//button[normalize-space()='닫기']",
            "//button[normalize-space()='확인']",
            "//button[contains(@class,'close')]",
        ]:
            try:
                btn = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
                btn.click()
            except Exception:
                pass

    # ---------- 조회 ----------
    def go_search(self):
        print(self.dpt_dt, self.arr_stn, self.dpt_tm)
        wait = WebDriverWait(self.driver, 15)

        self.driver.get("https://etk.srail.kr/hpg/hra/01/selectScheduleList.do")
        wait_until_queue_clears(self.driver, max_wait_sec=3600, poll=3)


        # 출발/도착역 입력
        dpt = wait.until(EC.element_to_be_clickable((By.ID, "dptRsStnCdNm")))
        dpt.clear()
        dpt.send_keys(self.dpt_stn)

        arv = wait.until(EC.element_to_be_clickable((By.ID, "arvRsStnCdNm")))
        arv.clear()
        arv.send_keys(self.arr_stn)

        # 날짜 선택
        dpt_dt_el = wait.until(EC.presence_of_element_located((By.ID, "dptDt")))
        self.driver.execute_script("arguments[0].style.display='block';", dpt_dt_el)
        Select(dpt_dt_el).select_by_value(self.dpt_dt)  # 예: "20250918"

        # 시간 선택
        dpt_tm_el = wait.until(EC.presence_of_element_located((By.ID, "dptTm")))
        self.driver.execute_script("arguments[0].style.display='block';", dpt_tm_el)
        Select(dpt_tm_el).select_by_visible_text(self.dpt_tm)

        # 조회하기
        query_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//*[self::input or self::button][@value='조회하기' or normalize-space()='조회하기']",
                )
            )
        )
        self.driver.execute_script("arguments[0].click();", query_btn)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#result-form table tbody tr")))
        time.sleep(0.5)

    def book_ticket(self, seat_label, i):
        """
        일반실(7열) 또는 '입석+좌석' 버튼 처리
        """
        label = (seat_label or "").strip()
        if not any(x in label for x in ["예약하기", "좌석선택", "입석+좌석"]):
            return None

        print(f"[{i}] 일반실 '{label}' 클릭")
        wait = WebDriverWait(self.driver, 10)

        sel = f"#result-form table tbody tr:nth-child({i}) td:nth-child(7) a"
        btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
        try:
            self.driver.execute_script("arguments[0].click();", btn)
        except ElementClickInterceptedException:
            try:
                btn.send_keys(Keys.ENTER)
            except Exception:
                pass

        # 입석+좌석은 alert이 뜨므로 자동 확인
        try:
            for _ in range(3):
                WebDriverWait(self.driver, 2).until(EC.alert_is_present())
                a = self.driver.switch_to.alert
                print(f"[ALERT] {a.text}")
                a.accept()
                time.sleep(0.3)
        except Exception:
            pass

        # 예약 성공 확인
        try:
            WebDriverWait(self.driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "isFalseGotoMain")),
                    EC.url_contains("selectReservationComplete"),
                )
            )
            self.is_booked = True
            print("예약 성공 ✅ (일반실/입석)")
            notify(f"[{i}] 예약 성공 ✅ (일반실/입석) 성공 ✅")  # ✅ 필요시 여기도 추가
            return self.driver
        except Exception:
            print("잔여석 없음/실패 → 뒤로가기(일반실)")
            self.driver.back()
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#result-form table tbody"))
            )
            return None

    def reserve_ticket(self, reservation, i):
        """
        8번째 열:
          - '입석+좌석' (문자에 '입석' 포함)  → 항상 클릭 + alert 자동 확인
          - '신청하기' → self.want_reserve 가 True일 때 클릭
        """
        label = (reservation or "").strip()
        wait = WebDriverWait(self.driver, 10)

        should_click = False
        if "입석" in label:
            should_click = True
        elif "신청하기" in label and self.want_reserve:
            should_click = True
        if not should_click:
            return False

        print(f"[{i}] 8열 '{label}' 클릭")
        sel = (
            f"#result-form table tbody tr:nth-child({i}) td:nth-child(8) a, "
            f"#result-form table tbody tr:nth-child({i}) td:nth-child(8) button"
        )
        btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
        try:
            self.driver.execute_script("arguments[0].click();", btn)
        except ElementClickInterceptedException:
            try:
                btn.send_keys(Keys.ENTER)
            except Exception:
                pass

        # alert 자동 확인 (연속으로 뜨는 경우도 처리)
        try:
            for _ in range(3):
                WebDriverWait(self.driver, 2).until(EC.alert_is_present())
                a = self.driver.switch_to.alert
                print(f"[ALERT] {a.text}")
                a.accept()
                time.sleep(0.3)
        except Exception:
            pass

        time.sleep(0.5)
        self.is_booked = True
        notify(f"[{i}] 입석/예약대기 성공 ✅")  # ✅ 필요시 여기도 추가
        return True

    def refresh_result(self):
        if self.stop_flag:
            return False
        wait = WebDriverWait(self.driver, 15)

        # 조회하기 클릭
        submit = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//*[self::input or self::button][@value='조회하기' or normalize-space()='조회하기']"
        )))
        self.driver.execute_script("arguments[0].click();", submit)

        # 대기열(큐) 모달이 다시 뜰 수 있음
        wait_until_queue_clears(self.driver, max_wait_sec=3600, poll=3)

        # 결과 나타나기/없음 배너/스피너 종료 중 하나만 만족되면 통과
        try:
            WebDriverWait(self.driver, 20).until(EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#result-form table tbody tr")),
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(.,'조회된 열차가 없습니다') or contains(.,'조회 결과가 없습니다')]")),
                # 스피너가 있다면: 사라질 때까지
                EC.invisibility_of_element_located((By.CSS_SELECTOR, ".loading, .spinner, .progress"))
            ))
        except Exception:
            # ❗타임아웃이라도 루프를 계속 돌게 한다 (서버가 느릴 때 대비)
            print("⚠️ 새로고침 후 결과 표시 지연(Timeout). 재시도합니다.")
            time.sleep(2)
            return False

        self.cnt_refresh += 1
        print(f"새로고침 {self.cnt_refresh}회")
        time.sleep(0.5)
        return True

    # ---------- 기타 ----------
    def stop(self):
        self.stop_flag = True
        self.close()

    def close(self):
        if self.driver:
            self.driver.quit()

    def get_train_list(self):
        trains = []
        for i in range(1, 11):
            try:
                info = self.driver.find_element(
                    By.CSS_SELECTOR,
                    f"#result-form table tbody tr:nth-child({i})",
                ).text
                trains.append({"index": i, "info": info})
            except NoSuchElementException:
                break
        return trains

    def check_selected_trains(self):
        consecutive_timeouts = 0
        while not self.stop_flag:
            for i in self.selected_trains:
                if self.stop_flag:
                    break
                try:
                    special_seat = self.driver.find_element(
                        By.CSS_SELECTOR, f"#result-form table tbody tr:nth-child({i}) > td:nth-child(6)"
                    ).text
                except (StaleElementReferenceException, NoSuchElementException):
                    special_seat = "매진"

                try:
                    standard_seat = self.driver.find_element(
                        By.CSS_SELECTOR, f"#result-form table tbody tr:nth-child({i}) > td:nth-child(7)"
                    ).text
                except (StaleElementReferenceException, NoSuchElementException):
                    standard_seat = "매진"

                try:
                    reservation = self.driver.find_element(
                        By.CSS_SELECTOR, f"#result-form table tbody tr:nth-child({i}) > td:nth-child(8)"
                    ).text
                except (StaleElementReferenceException, NoSuchElementException):
                    reservation = "매진"

                # 우선순위: 특실 → 일반실 → 예약대기/입석
                if self.book_special_ticket(special_seat, i):
                    return self.driver
                if self.book_ticket(standard_seat, i):
                    return self.driver
                if self.reserve_ticket(reservation, i):
                    return self.driver

            if self.is_booked:
                return self.driver

            time.sleep(randint(2, 4))
            ok = self.refresh_result()
            if not ok:
                consecutive_timeouts += 1
                if consecutive_timeouts % 3 == 0:
                    time.sleep(5)
            else:
                consecutive_timeouts = 0


# _queue_active() 교체
def _queue_active(driver) -> Optional[int]:
    try:
        body_text = driver.execute_script("return document.body.innerText || ''")
        if re.search(r"접속\s*대기\s*중입니다", body_text) or ("나의 대기 순서" in body_text):
            m = re.search(r"나의\s*대기\s*순서\s*([\d,]+)\s*명", body_text)
            return int(m.group(1).replace(",", "")) if m else -1
        overlay = driver.find_elements(By.XPATH,
            "//*[contains(.,'접속대기 중입니다') or contains(.,'나의 대기 순서')]")
        return -1 if any(el.is_displayed() for el in overlay) else None
    except Exception:
        return None



def wait_until_queue_clears(driver, max_wait_sec=3600, poll=3):
    start = time.time()
    last_log = 0
    while True:
        num = _queue_active(driver)
        if num is None:
            return
        now = time.time()
        if now - last_log > 5:
            print(f"[QUEUE] 접속 대기 중… 순번: {num if num >= 0 else '확인 중'}")
            last_log = now
        if now - start > max_wait_sec:
            raise TimeoutError("대기열이 사라지지 않습니다. max_wait_sec 초과")
        time.sleep(poll)


