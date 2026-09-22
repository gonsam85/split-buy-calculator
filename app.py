import json
import math
import os
import re

import pandas as pd
import streamlit as st
import yfinance as yf

WATCHLIST_FILE = "watchlist.json"


def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_watchlist(watchlist):
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False)
    except Exception:
        pass


SAVED_PLANS_FILE = "saved_plans.json"


def load_saved_plans():
    if os.path.exists(SAVED_PLANS_FILE):
        try:
            with open(SAVED_PLANS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_saved_plans(plans):
    try:
        with open(SAVED_PLANS_FILE, "w", encoding="utf-8") as f:
            json.dump(plans, f, ensure_ascii=False, indent=2)
    except Exception:
        pass



st.set_page_config(page_title="분할매수 계산기", page_icon="icon.png", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
    html, body, [class*="css"], .stApp, .stMarkdown, .stMetric, button, input, textarea, select {
        font-family: 'Space Grotesk', sans-serif !important;
    }
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextInput"] input,
    div[data-baseweb="select"] > div {
        background-color: var(--secondary-background-color) !important;
        border-radius: 8px !important;
        border: 1px solid rgba(128,128,128,0.25) !important;
    }
    div[data-testid="stForm"] {
        background-color: var(--secondary-background-color);
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid rgba(128,128,128,0.15);
    }
    button[kind="primary"], button[kind="secondary"], .stButton button {
        border-radius: 8px !important;
    }
    div[data-baseweb="tab-list"] {
        gap: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

title_icon_col, title_text_col = st.columns([1, 12], vertical_alignment="center")
with title_icon_col:
    st.image("icon.png", width=42)
with title_text_col:
    st.markdown(
        "<h1 style='font-size:1.5rem; font-weight:700; white-space:nowrap; margin-bottom:0.2rem;'>분할매수 계산기</h1>",
        unsafe_allow_html=True,
    )
st.caption("종목명이나 티커를 검색하면 야후 파이낸스에서 최고가·MDD 데이터를 실시간으로 가져와 분할매수 계획을 세워드려요. 한국·미국 주식 모두 검색할 수 있어요.")
st.caption("💡 라이트/다크 모드는 오른쪽 위 ⋮ 메뉴 → Settings → Theme에서 바꿀 수 있어요.")

# 좌측 네온 보더 포인트 카드 — 배경/글자색은 Streamlit 테마 변수를 써서
# 라이트/다크 모드 어느 쪽이든 자동으로 맞춰지도록 함
ACCENT = {
    "green": {"border": "#00C389"},
    "danger": {"border": "#E5384F"},
}


def render_html_table(df: pd.DataFrame, cell_styles: dict = None, row_style_fn=None) -> str:
    """모든 셀과 헤더를 가운데 정렬한 HTML 표. cell_styles: {컬럼명: 추가 스타일},
    row_style_fn: 행 인덱스를 받아 그 행 전체에 적용할 스타일 문자열을 반환."""
    cell_styles = cell_styles or {}
    thead = "".join(
        f"<th style='text-align:center; padding:8px 10px; border-bottom:1px solid rgba(128,128,128,0.25);"
        f" font-weight:600; font-size:12px; color:var(--text-color); opacity:0.7; white-space:nowrap;'>{col}</th>"
        for col in df.columns
    )
    rows_html = ""
    for idx, row in df.iterrows():
        row_extra = row_style_fn(idx) if row_style_fn else ""
        cells = ""
        for col in df.columns:
            col_style = cell_styles.get(col, "")
            cells += (
                f"<td style='text-align:center; padding:8px 10px; white-space:nowrap;"
                f" border-bottom:1px solid rgba(128,128,128,0.15); color:var(--text-color); {row_extra} {col_style}'>"
                f"{row[col]}</td>"
            )
        rows_html += f"<tr>{cells}</tr>"
    return f"""
    <div style="overflow-x:auto;">
    <table style="width:100%; min-width:max-content; border-collapse:collapse; font-size:13px;">
      <thead><tr>{thead}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """


def metric_card_html(label: str, value: str, accent: str = "green") -> str:
    border = ACCENT[accent]["border"]
    return f"""
    <div style="background:var(--secondary-background-color); border-radius:10px; padding:0.85rem 1rem;
                border-left:3px solid {border}; box-shadow:0 1px 2px rgba(0,0,0,0.06); min-width:0;">
        <div style="font-size:11.5px; color:var(--text-color); opacity:0.6; margin-bottom:3px;
                    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{label}</div>
        <div style="font-size:clamp(11px, 4vw, 17px); font-weight:700; color:var(--text-color);
                    line-height:1.25; white-space:nowrap; overflow:hidden;">{value}</div>
    </div>
    """


def metric_card_html_big(label: str, value: str, accent: str = "green") -> str:
    border = ACCENT[accent]["border"]
    return f"""
    <div style="background:var(--secondary-background-color); border-radius:12px; padding:1.1rem 1.3rem;
                border-left:4px solid {border}; box-shadow:0 1px 3px rgba(0,0,0,0.08); min-width:0;">
        <div style="font-size:12.5px; color:var(--text-color); opacity:0.6; margin-bottom:6px;
                    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{label}</div>
        <div style="font-size:clamp(20px, 7.5vw, 30px); font-weight:700; color:var(--text-color);
                    line-height:1.2; white-space:nowrap; overflow:hidden;">{value}</div>
    </div>
    """


def metric_row_html(cards: list) -> str:
    cols = "".join(f'<div style="min-width:0;">{html}</div>' for html in cards)
    return f'<div style="display:grid; grid-template-columns:repeat({len(cards)}, 1fr); gap:10px; margin-bottom:1rem;">{cols}</div>'

DIRECT_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")

RATIO_METHODS = ["균등분할", "피라미딩 (하락시 확대)", "역피라미딩 (초반 확대)", "마틴게일 (직전 2배)", "피보나치", "직접 입력"]


def fmt_price(value: float, currency: str) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    if currency == "KRW":
        return f"{sign}{value:,.0f}원"
    return f"{sign}${value:,.2f}"


def generate_ratios(method: str, rounds: int):
    if method == "균등분할":
        return [1.0] * rounds
    if method == "피라미딩 (하락시 확대)":
        return [1 + 0.5 * i for i in range(rounds)]
    if method == "역피라미딩 (초반 확대)":
        return [1 + 0.5 * i for i in range(rounds)][::-1]
    if method == "마틴게일 (직전 2배)":
        return [float(2 ** i) for i in range(rounds)]
    if method == "피보나치":
        seq = [1.0, 1.0]
        while len(seq) < rounds:
            seq.append(seq[-1] + seq[-2])
        return seq[:rounds] if rounds >= 2 else seq[:1]
    return [1.0] * rounds


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ticker_data(symbol: str):
    t = yf.Ticker(symbol)
    hist = t.history(period="1y")
    if hist.empty:
        return None
    try:
        info = t.info
    except Exception:
        info = {}
    name = info.get("longName") or info.get("shortName") or symbol
    currency = info.get("currency") or ("KRW" if symbol.upper().endswith((".KS", ".KQ")) else "USD")
    return {
        "symbol": symbol.upper(),
        "name": name,
        "currency": currency,
        "current_price": float(hist["Close"].iloc[-1]),
        "high_52w": float(hist["High"].max()),
        "low_52w": float(hist["Low"].min()),
    }


def direct_symbol_candidates(query: str):
    q = query.strip()
    if not DIRECT_SYMBOL_RE.match(q):
        return []
    if q.isdigit() and len(q) == 6:
        # 한국 종목코드로 추정 — 코스피, 코스닥 순으로 시도
        return [f"{q}.KS", f"{q}.KQ"]
    return [q.upper()]


@st.cache_data(ttl=600, show_spinner=False)
def search_candidates(query: str):
    try:
        res = yf.Search(query, max_results=8)
    except TypeError:
        res = yf.Search(query)
    except Exception:
        return []
    quotes = getattr(res, "quotes", None) or []
    out = []
    for q in quotes:
        symbol = q.get("symbol")
        if not symbol:
            continue
        out.append(
            {
                "symbol": symbol,
                "name": q.get("shortname") or q.get("longname") or symbol,
                "exchange": q.get("exchDisp") or q.get("exchange") or "",
            }
        )
    return out


def try_resolve_direct(query: str):
    for candidate in direct_symbol_candidates(query):
        data = fetch_ticker_data(candidate)
        if data:
            return data
    return None


if "data" not in st.session_state:
    with st.spinner("데이터를 불러오는 중..."):
        st.session_state["data"] = fetch_ticker_data("TQQQ")
if "search_results" not in st.session_state:
    st.session_state["search_results"] = []
if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = load_watchlist()
if "saved_plans" not in st.session_state:
    st.session_state["saved_plans"] = load_saved_plans()
if "pending_load_plan" not in st.session_state:
    st.session_state["pending_load_plan"] = None

# 저장된 설정 불러오기는 위젯이 이미 생성된 뒤에는 session_state를 바꿀 수 없어서,
# 다음 재실행 맨 앞(위젯 생성 전)에서 한 번에 반영함
if st.session_state["pending_load_plan"]:
    _p = st.session_state["pending_load_plan"]
    st.session_state[f"total_amount_{_p['symbol']}"] = _p["total_amount"]
    st.session_state[f"ratio_method_{_p['symbol']}"] = _p["ratio_method"]
    if _p["ratio_method"] == "직접 입력":
        st.session_state[f"custom_ratio_{_p['symbol']}"] = _p["custom_ratio_text"]
    else:
        st.session_state[f"rounds_{_p['symbol']}"] = _p["rounds"]
    st.session_state[f"start_price_{_p['symbol']}"] = _p["start_price"]
    st.session_state[f"drop_pct_{_p['symbol']}"] = _p["drop_pct"]
    st.session_state[f"target_price_{_p['symbol']}"] = _p["target_price"]
    st.session_state["pending_load_plan"] = None

col_input, col_main = st.columns([1, 2], gap="large")

with col_input:
    st.subheader("종목 검색")
    with st.form("search_form"):
        query = st.text_input("종목명 또는 티커", placeholder="예: TQQQ, 삼성전자, 005930, Apple")
        searched = st.form_submit_button("검색", use_container_width=True)

    if searched and query.strip():
        with st.spinner("검색 중..."):
            direct_hit = try_resolve_direct(query)
        if direct_hit:
            st.session_state["data"] = direct_hit
            st.session_state["search_results"] = []
        else:
            with st.spinner("종목명으로 검색 중..."):
                candidates = search_candidates(query)
            if candidates:
                st.session_state["search_results"] = candidates
            else:
                st.session_state["search_results"] = []
                st.error("일치하는 종목을 찾을 수 없어요. 정확한 티커나 종목명으로 다시 검색해주세요.")

    if st.session_state["search_results"]:
        options = st.session_state["search_results"]
        labels = [f"{o['symbol']} · {o['name']} ({o['exchange']})" for o in options]
        picked = st.radio("검색 결과", labels, index=0, label_visibility="collapsed")
        if st.button("이 종목 선택", use_container_width=True):
            picked_symbol = options[labels.index(picked)]["symbol"]
            with st.spinner(f"{picked_symbol} 데이터를 불러오는 중..."):
                fetched = fetch_ticker_data(picked_symbol)
            if fetched:
                st.session_state["data"] = fetched
                st.session_state["search_results"] = []
                st.rerun()
            else:
                st.error("해당 종목의 데이터를 가져오지 못했어요.")

    if st.session_state["watchlist"]:
        st.markdown(
            "<div style='font-size:11.5px; color:#6B7885; margin:10px 0 4px;'>⭐ 관심종목</div>",
            unsafe_allow_html=True,
        )
        for w in st.session_state["watchlist"]:
            wl_col1, wl_col2 = st.columns([4, 1])
            if wl_col1.button(f"{w['symbol']} · {w['name']}", key=f"wl_go_{w['symbol']}", use_container_width=True):
                with st.spinner(f"{w['symbol']} 데이터를 불러오는 중..."):
                    fetched = fetch_ticker_data(w["symbol"])
                if fetched:
                    st.session_state["data"] = fetched
                    st.rerun()
                else:
                    st.error("해당 종목의 데이터를 가져오지 못했어요.")
            if wl_col2.button("✕", key=f"wl_del_{w['symbol']}"):
                st.session_state["watchlist"] = [x for x in st.session_state["watchlist"] if x["symbol"] != w["symbol"]]
                save_watchlist(st.session_state["watchlist"])
                st.rerun()

data = st.session_state.get("data")

if data:
    currency = data["currency"]
    # MDD = 52주 최고가 대비 현재가의 하락률
    mdd = (data["high_52w"] - data["current_price"]) / data["high_52w"] * 100
    step = 0.01 if currency != "KRW" else 100.0
    num_format = "%.2f" if currency != "KRW" else "%.0f"

    with col_input:
        st.divider()
        cap_col, star_col = st.columns([3, 1])
        cap_col.caption(f"{data['symbol']} · {data['name']}")
        in_watchlist = any(w["symbol"] == data["symbol"] for w in st.session_state["watchlist"])
        star_label = "★ 제거" if in_watchlist else "☆ 추가"
        if star_col.button(star_label, key="watchlist_toggle", use_container_width=True):
            if in_watchlist:
                st.session_state["watchlist"] = [
                    w for w in st.session_state["watchlist"] if w["symbol"] != data["symbol"]
                ]
            else:
                st.session_state["watchlist"].append({"symbol": data["symbol"], "name": data["name"]})
            save_watchlist(st.session_state["watchlist"])
            st.rerun()
        st.markdown(
            metric_row_html(
                [
                    metric_card_html("현재가", fmt_price(data["current_price"], currency), "green"),
                    metric_card_html("52주 최고가", fmt_price(data["high_52w"], currency), "green"),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            metric_row_html(
                [
                    metric_card_html("52주 최저가", fmt_price(data["low_52w"], currency), "green"),
                    metric_card_html(
                        "MDD (최고가 대비 현재가)", f"{'-' if mdd > 0 else ''}{mdd:.1f}%", "danger" if mdd > 0 else "green"
                    ),
                ]
            ),
            unsafe_allow_html=True,
        )

        st.divider()
        st.subheader("매수 조건")
        amount_step = 10000.0 if currency == "KRW" else 100.0
        total_amount = st.number_input(
            f"총 투자금액 ({currency})", min_value=0.0,
            value=float(5000 if currency != "KRW" else 5000000), step=amount_step,
            key=f"total_amount_{data['symbol']}",
        )

        ratio_method = st.selectbox("분할 비율 방식", RATIO_METHODS, key=f"ratio_method_{data['symbol']}")

        custom_ratio_list = None
        if ratio_method == "직접 입력":
            custom_text = st.text_input(
                "비율 입력 (쉼표로 구분)",
                value="1, 1.5, 2, 2.5, 3",
                help="회차별 투입 비율을 쉼표로 구분해서 입력하세요. 입력한 개수만큼 회차수가 정해져요.",
                key=f"custom_ratio_{data['symbol']}",
            )
            try:
                parsed = [float(x.strip()) for x in custom_text.split(",") if x.strip() != ""]
            except ValueError:
                parsed = []
            if not parsed or any(v < 0 for v in parsed):
                st.error("숫자와 쉼표만 사용해주세요. 예: 1, 1.5, 2, 2.5, 3")
                parsed = [1.0]
            custom_ratio_list = parsed
            rounds = len(custom_ratio_list)
            st.caption(f"총 {rounds}회차로 설정돼요.")
        else:
            rounds = st.number_input(
                "분할 회차수", min_value=2, max_value=30, value=5, step=1, key=f"rounds_{data['symbol']}"
            )

        start_price = st.number_input(
            f"매수 시작가 ({currency})", min_value=0.0, value=round(data["current_price"], 2), step=step, format=num_format,
            key=f"start_price_{data['symbol']}",
        )
        drop_pct = st.number_input(
            "회차마다 하락률 (%)", min_value=0.1, max_value=50.0, value=5.0, step=0.5,
            help="직전 회차 매수가 대비 이만큼 떨어질 때마다 다음 회차를 매수해요.",
            key=f"drop_pct_{data['symbol']}",
        )

        ratio_list = custom_ratio_list if custom_ratio_list is not None else generate_ratios(ratio_method, int(rounds))
        ratio_sum = sum(ratio_list) or 1.0
        ratio_display = " : ".join(f"{r:g}" for r in ratio_list)
        st.caption(f"투입 비율 — {ratio_display}")

    # 회차별 원자료(raw)를 미리 계산해두고 두 탭(매수 계획 / 통계)에서 함께 사용
    drop_ratio = drop_pct / 100
    ladder = []
    cum_qty = 0.0
    cum_amount = 0.0
    for i in range(int(rounds)):
        price = start_price * ((1 - drop_ratio) ** i)
        planned_amount = total_amount * (ratio_list[i] / ratio_sum)
        qty = math.floor(planned_amount / price) if price > 0 else 0  # 정해진 금액을 넘지 않도록 내림 처리
        actual_amount = qty * price
        cum_qty += qty
        cum_amount += actual_amount
        avg_price = cum_amount / cum_qty if cum_qty > 0 else 0
        ladder.append(
            {
                "i": i,
                "price": price,
                "from_high_pct": (1 - (1 - drop_ratio) ** i) * 100,
                "ratio": ratio_list[i],
                "planned_amount": planned_amount,
                "amount": actual_amount,
                "qty": qty,
                "cum_qty": cum_qty,
                "avg_price": avg_price,
            }
        )

    with col_main:
        tab_plan, tab_stats = st.tabs(["매수 계획", "통계"])

        with tab_plan:
            st.subheader("분할매수 계획")

            df = pd.DataFrame(
                [
                    {
                        "회차": f"{r['i'] + 1}회차",
                        "매수가": fmt_price(r["price"], currency),
                        "고점 대비": f"-{r['from_high_pct']:.1f}%",
                        "비율": f"{r['ratio']:g}",
                        "회차 투자금": fmt_price(r["amount"], currency),
                        "매수 수량 (주)": int(r["qty"]),
                        "누적 수량 (주)": int(r["cum_qty"]),
                        "누적 평단가": fmt_price(r["avg_price"], currency),
                    }
                    for r in ladder
                ]
            )

            st.markdown(
                render_html_table(
                    df, cell_styles={"매수가": "font-weight:700; font-size:15px; color:#00A876;"}
                ),
                unsafe_allow_html=True,
            )
            st.caption("매수 수량은 소수점을 버리고 정수 주 단위로 계산해서, 회차별 투자금을 넘지 않도록 했어요.")

            if ladder:
                final_avg_val = ladder[-1]["avg_price"]
                final_qty = ladder[-1]["cum_qty"]
                pnl_pct = (data["current_price"] - final_avg_val) / final_avg_val * 100 if final_avg_val > 0 else 0

                st.markdown(
                    metric_row_html(
                        [
                            metric_card_html("완료 시 평단가", fmt_price(final_avg_val, currency), "green"),
                            metric_card_html("총 매수 수량", f"{final_qty:.0f}주", "green"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    metric_card_html_big(
                        "현재가 대비 손익률", f"{pnl_pct:+.1f}%", "green" if pnl_pct >= 0 else "danger"
                    ),
                    unsafe_allow_html=True,
                )

            st.caption("※ 시세는 최대 5분 캐시되어 표시돼요. 매매 전에는 반드시 증권사 앱에서 실제 시세를 확인하세요.")

        with tab_stats:
            st.subheader("목표가 통계")
            target_price = st.number_input(
                f"목표가 ({currency})",
                min_value=0.0,
                value=round(data["high_52w"], 2),
                step=step,
                format=num_format,
                key=f"target_price_{data['symbol']}",
            )

            st.caption("표는 가로로 스크롤해서 볼 수 있어요. (수익률·수익금은 위 목표가 기준이에요)")

            completed_rounds = st.slider(
                "매수 완료 회차 (여기까지 매수했어요)",
                min_value=0,
                max_value=len(ladder),
                value=min(st.session_state.get(f"completed_{data['symbol']}", 0), len(ladder)),
                key=f"completed_{data['symbol']}",
            )

            stats_rows = []
            for r in ladder:
                pnl_pct = (target_price - r["avg_price"]) / r["avg_price"] * 100 if r["avg_price"] > 0 else 0
                pnl_amt = (target_price - r["avg_price"]) * r["cum_qty"]
                pnl_color = "#00A876" if pnl_pct >= 0 else "#E5384F"
                stats_rows.append(
                    {
                        "완료": "✓" if r["i"] < completed_rounds else "",
                        "회차": f"{r['i'] + 1}회차",
                        "매수가": fmt_price(r["price"], currency),
                        "누적평단가": fmt_price(r["avg_price"], currency),
                        "수익률": f"<span style='color:{pnl_color}; font-weight:600;'>{pnl_pct:+.1f}%</span>",
                        "수익금": f"<span style='color:{pnl_color}; font-weight:600;'>{fmt_price(pnl_amt, currency)}</span>",
                    }
                )
            stats_df = pd.DataFrame(stats_rows)

            def stats_row_style(idx):
                if idx < completed_rounds:
                    return "color:#00A876; font-weight:700;"
                return "opacity:0.45;"

            st.markdown(
                render_html_table(stats_df, row_style_fn=stats_row_style),
                unsafe_allow_html=True,
            )

            if completed_rounds > 0:
                last_bought = ladder[completed_rounds - 1]
                st.divider()
                cur_pnl = (target_price - last_bought["avg_price"]) / last_bought["avg_price"] * 100 if last_bought["avg_price"] > 0 else 0
                cur_pnl_amt = (target_price - last_bought["avg_price"]) * last_bought["cum_qty"]
                st.markdown(
                    metric_row_html(
                        [
                            metric_card_html("매수 완료 회차", f"{completed_rounds} / {len(ladder)}회차", "green"),
                            metric_card_html("현재까지 평단가", fmt_price(last_bought["avg_price"], currency), "green"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    metric_row_html(
                        [
                            metric_card_html_big(
                                "수익률", f"{cur_pnl:+.1f}%", "green" if cur_pnl >= 0 else "danger"
                            ),
                            metric_card_html_big(
                                "수익금", fmt_price(cur_pnl_amt, currency), "green" if cur_pnl_amt >= 0 else "danger"
                            ),
                        ]
                    ),
                    unsafe_allow_html=True,
                )

        st.divider()
        st.subheader("💾 이 설정 저장하기")
        save_col1, save_col2 = st.columns([3, 1])
        default_plan_name = f"{data['symbol']} 플랜"
        plan_name = save_col1.text_input("설정 이름", value=default_plan_name, key="plan_name_input", label_visibility="collapsed", placeholder="설정 이름")
        if save_col2.button("저장", use_container_width=True):
            new_plan = {
                "name": plan_name.strip() or default_plan_name,
                "symbol": data["symbol"],
                "currency": currency,
                "total_amount": total_amount,
                "ratio_method": ratio_method,
                "custom_ratio_text": st.session_state.get(f"custom_ratio_{data['symbol']}", ""),
                "rounds": int(rounds),
                "start_price": start_price,
                "drop_pct": drop_pct,
                "target_price": st.session_state.get(f"target_price_{data['symbol']}", round(data["high_52w"], 2)),
            }
            st.session_state["saved_plans"].append(new_plan)
            save_saved_plans(st.session_state["saved_plans"])
            st.success(f"'{new_plan['name']}' 설정을 저장했어요.")

        my_plans = [p for p in st.session_state["saved_plans"] if p["symbol"] == data["symbol"]]
        if my_plans:
            st.caption(f"{data['symbol']}로 저장된 설정")
            for idx, p in enumerate(my_plans):
                p_col1, p_col2 = st.columns([4, 1])
                if p_col1.button(f"📂 {p['name']}", key=f"load_plan_{data['symbol']}_{idx}", use_container_width=True):
                    st.session_state["pending_load_plan"] = p
                    st.rerun()
                if p_col2.button("✕", key=f"del_plan_{data['symbol']}_{idx}"):
                    st.session_state["saved_plans"] = [
                        x for x in st.session_state["saved_plans"] if x is not p
                    ]
                    save_saved_plans(st.session_state["saved_plans"])
                    st.rerun()
else:
    st.info("종목을 검색해주세요.")
