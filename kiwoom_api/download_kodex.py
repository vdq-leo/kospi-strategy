import os
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 1. ĐIỀN THÔNG TIN API CỦA BẠN VÀO ĐÂY
# ==========================================
API_KEY = "JKrsQnDDE2GL2ytobjpl8TDPXKdbomImjD758B4_aTc"
SECRET_KEY = "ck5oXSsRYdJOE__YbEq3ytXfFGi9QOWFiUSqr1dysIQ"

# Cấu hình tải dữ liệu
STOCK_CODE = "069500"           # Mã KODEX 200
TIC_SCOPE  = "1"                # Nến 1 phút
OUTPUT_CSV = "kodex200_1m_real.csv"  # Tên file xuất ra
DELAY_SEC  = 0.5                # Thời gian nghỉ giữa các lần gọi API (chống ban)
TARGET_YEARS = 3                # Số năm muốn lấy lùi lại từ hiện tại
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kodex_fetcher")


class KiwoomRESTClient:
    """Client mini để xử lý OAuth và gọi Kiwoom REST API"""
    def __init__(self, appkey, secretkey):
        self.appkey = appkey
        self.secretkey = secretkey
        self.base_url = "https://api.kiwoom.com"
        self.token = None

    def _get_headers(self, api_id: str, cont_yn: str = "N", next_key: str = "") -> dict:
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": api_id,
            "cont-yn": cont_yn
        }
        if next_key:
            headers["next-key"] = next_key
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        return headers

    def get_access_token(self) -> str:
        url = f"{self.base_url}/oauth2/token"
        headers = self._get_headers(api_id="au10001")
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.appkey,
            "secretkey": self.secretkey
        }
        logger.info("Đang lấy access token từ Kiwoom...")
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        
        if data.get("return_code") != 0:
            raise Exception(f"Lỗi khi lấy token: {data.get('return_msg')} (code: {data.get('return_code')})")
            
        self.token = data["token"]
        logger.info("✅ Lấy token thành công!")
        return self.token


def fetch_minute_chart_page(client: KiwoomRESTClient, cont_yn: str = "N", next_key: str = "") -> dict:
    """Gửi request lấy 1 trang nến phút"""
    url = f"{client.base_url}/api/dostk/chart"
    headers = client._get_headers(api_id="ka10080", cont_yn=cont_yn, next_key=next_key)
    payload = {
        "stk_cd": STOCK_CODE,
        "tic_scope": TIC_SCOPE,
        "upd_stkpc_tp": "1",   # Lấy giá đã điều chỉnh (adjusted price)
    }

    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    return {
        "body": res.json(),
        "resp_cont_yn": res.headers.get("cont-yn", "N"),
        "resp_next_key": res.headers.get("next-key", ""),
    }


def parse_candles(raw_list: list) -> pd.DataFrame:
    """Chuyển đổi dữ liệu JSON thô thành DataFrame"""
    rows = []
    for c in raw_list:
        dt_str = c.get("cntr_tm", "")  # Tên trường thời gian là cntr_tm
        if not dt_str or len(dt_str) < 12:
            continue
        try:
            dt = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S")
        except ValueError:
            continue
        
        # Lấy giá trị tuyệt đối abs() vì Kiwoom đôi khi trả số âm cho nến giảm
        rows.append({
            "datetime": dt,
            "open":   abs(float(c.get("open_pric", 0))),
            "high":   abs(float(c.get("high_pric", 0))),
            "low":    abs(float(c.get("low_pric", 0))),
            "close":  abs(float(c.get("cur_prc", 0))),
            "volume": abs(int(c.get("trde_qty", 0))),
        })
        
    if not rows:
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
    
    df = pd.DataFrame(rows)
    df.sort_values("datetime", inplace=True)
    df.drop_duplicates(subset="datetime", keep="first", inplace=True)
    return df



def fetch_all():
    """Tải toàn bộ dữ liệu theo số năm yêu cầu"""
    if API_KEY == "YOUR_API_KEY_HERE" or SECRET_KEY == "YOUR_SECRET_KEY_HERE":
        logger.error("Vui lòng cập nhật API_KEY và SECRET_KEY của bạn vào file code trước khi chạy!")
        return
        
    client = KiwoomRESTClient(appkey=API_KEY, secretkey=SECRET_KEY)
    client.get_access_token()
    
    existing_df = pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
    if os.path.exists(OUTPUT_CSV) and os.path.getsize(OUTPUT_CSV) > 0:
        existing_df = pd.read_csv(OUTPUT_CSV, parse_dates=["datetime"])
        logger.info(f"Đã nạp {len(existing_df)} dòng từ dữ liệu cũ trong {OUTPUT_CSV}")

    cutoff = datetime.now() - timedelta(days=TARGET_YEARS * 365)
    all_new = []
    cont_yn = "N"
    next_key = ""
    page = 0
    oldest_seen = datetime.now()

    logger.info(f"Bắt đầu tải KODEX 200 lùi về đến {cutoff.date()}...")

    while True:
        page += 1
        logger.info(f"Trang {page}: cont_yn={cont_yn}, next_key={next_key[:30]}...")

        try:
            result = fetch_minute_chart_page(client, cont_yn=cont_yn, next_key=next_key)
        except Exception as e:
            logger.error(f"Lỗi API ở trang {page}: {e}")
            break

        body = result["body"]
        if body.get("return_code") != 0:
            logger.warning(f"Kiwoom trả về lỗi: {body.get('return_msg')}")
            break

        raw_candles = body.get("stk_min_pole_chart_qry", [])
        if not raw_candles:
            logger.info("Không có dữ liệu nến trả về. Hoàn thành!")
            break

        page_df = parse_candles(raw_candles)
        if page_df.empty:
            logger.info("Dữ liệu nến không hợp lệ. Hoàn thành!")
            break

        all_new.append(page_df)
        page_oldest = page_df["datetime"].min()
        page_newest = page_df["datetime"].max()
        oldest_seen = min(oldest_seen, page_oldest)

        logger.info(f"  -> Lấy được {len(page_df)} nến, ngày cũ nhất trang này: {page_oldest.date()}")

        if oldest_seen < cutoff:
            logger.info(f"Đã chạm mốc {cutoff.date()}. Dừng lấy dữ liệu.")
            break

        resp_cont = result["resp_cont_yn"]
        resp_next = result["resp_next_key"]

        if resp_cont.upper() != "Y" or not resp_next:
            logger.info("Kiwoom báo không còn trang nào nữa. Hoàn thành!")
            break

        cont_yn = "Y"
        next_key = resp_next

        # Lưu trung gian mỗi 50 trang để tránh mất mát nếu rớt mạng
        if page % 50 == 0:
            interim = pd.concat([existing_df] + all_new, ignore_index=True)
            interim.drop_duplicates(subset="datetime", keep="first", inplace=True)
            interim.sort_values("datetime", inplace=True)
            interim.to_csv(OUTPUT_CSV, index=False)
            logger.info(f"Đã lưu tiến độ vào {OUTPUT_CSV}")

        time.sleep(DELAY_SEC)

    if all_new:
        final_df = pd.concat([existing_df] + all_new, ignore_index=True)
    else:
        final_df = existing_df

    final_df.drop_duplicates(subset="datetime", keep="first", inplace=True)
    final_df.sort_values("datetime", inplace=True)
    final_df.reset_index(drop=True, inplace=True)
    final_df.to_csv(OUTPUT_CSV, index=False)
    
    logger.info("=" * 60)
    logger.info("HOÀN TẤT TẢI DỮ LIỆU!")
    logger.info(f"Tổng số dòng  : {len(final_df)}")
    if not final_df.empty:
        logger.info(f"Từ ngày       : {final_df['datetime'].min()}")
        logger.info(f"Đến ngày      : {final_df['datetime'].max()}")
    logger.info("=" * 60)

if __name__ == "__main__":
    fetch_all()
