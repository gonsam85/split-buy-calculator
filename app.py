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



st.set_page_config(page_title="분할매수 계산기", page_icon="📉", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
    html, body, [class*="css"], .stApp, .stMarkdown, .stMetric, button, input, textarea, select {
        font-family: 'Space Grotesk', sans-serif !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📉 분할매수 계산기")
st.caption("종목명이나 티커를 검색하면 야후 파이낸스에서 최고가·MDD 데이터를 실시간으로 가져와 분할매수 계획을 세워드려요. 한국·미국 주식 모두 검색할 수 있어요.")
st.caption("💡 라이트/다크 모드는 오른쪽 위 ⋮ 메뉴 → Settings → Theme에서 바꿀 수 있어요.")

# 네오 핀테크 스타일 카드 (짙은 배경 + 네온 포인트 좌측 보더)
ACCENT = {
    "green": {"border": "#00E5A0", "label": "#6B7885", "value": "#E8ECEC"},
    "danger": {"border": "#FF3B6B", "label": "#FF8FA8", "value": "#FF3B6B"},
}


def metric_card_html(label: str, value: str, accent: str = "green") -> str:
    c = ACCENT[accent]
    return f"""
    <div style="background:#10151B; border-radius:10px; padding:0.85rem 1rem; border-left:3px solid {c['border']};">
        <div style="font-size:11.5px; color:{c['label']}; margin-bottom:3px;">{label}</div>
        <div style="font-size:17px; font-weight:700; color:{c['value']};">{value}</div>
    </div>
    """


def metric_row_html(cards: list) -> str:
    cols = "".join(f'<div>{html}</div>' for html in cards)
    return f'<div style="display:grid; grid-template-columns:repeat({len(cards)}, 1fr); gap:10px; margin-bottom:1rem;">{cols}</div>'

DIRECT_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")

RATIO_METHODS = ["균등분할", "피라미딩 (하락시 확대)", "역피라미딩 (초반 확대)", "마틴게일 (직전 2배)", "피보나치", "직접 입력"]


def fmt_price(value: float, currency: str) -> str:
    if currency == "KRW":
        return f"{value:,.0f}원"
    return f"${value:,.2f}"


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
                    metric_card_html("MDD (최고가 대비 현재가)", f"-{mdd:.1f}%", "danger"),
                ]
            ),
            unsafe_allow_html=True,
        )

        st.divider()
        st.subheader("매수 조건")
        amount_step = 10000.0 if currency == "KRW" else 100.0
        total_amount = st.number_input(
            f"총 투자금액 ({currency})", min_value=0.0, value=float(5000 if currency != "KRW" else 5000000), step=amount_step
        )

        ratio_method = st.selectbox("분할 비율 방식", RATIO_METHODS)

        custom_ratio_list = None
        if ratio_method == "직접 입력":
            custom_text = st.text_input(
                "비율 입력 (쉼표로 구분)",
                value="1, 1.5, 2, 2.5, 3",
                help="회차별 투입 비율을 쉼표로 구분해서 입력하세요. 입력한 개수만큼 회차수가 정해져요.",
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
            rounds = st.number_input("분할 회차수", min_value=2, max_value=30, value=5, step=1)

        start_price = st.number_input(
            f"매수 시작가 ({currency})", min_value=0.0, value=round(data["current_price"], 2), step=step, format=num_format
        )
        drop_pct = st.number_input(
            "회차마다 하락률 (%)", min_value=0.1, max_value=50.0, value=5.0, step=0.5,
            help="직전 회차 매수가 대비 이만큼 떨어질 때마다 다음 회차를 매수해요."
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

            styled = df.style.set_properties(
                subset=["매수가"], **{"font-weight": "700", "font-size": "15px", "color": "#00E5A0"}
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
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
                            metric_card_html(
                                "현재가 대비 손익률", f"{pnl_pct:+.1f}%", "green" if pnl_pct >= 0 else "danger"
                            ),
                        ]
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
                key="target_price",
            )

            st.caption("회차를 체크하면 실제 매수한 회차로 표시돼요.")
            st.write("")

            header_cols = st.columns([0.5, 0.9, 1.2, 1.3, 1.6, 1.6])
            for c, h in zip(header_cols, ["완료", "회차", "매수가", "누적평단가", "목표가 달성시 수익률", "목표가 달성시 수익금"]):
                c.markdown(f"**{h}**")

            prev_checked = True
            for r in ladder:
                bought_key = f"bought_{data['symbol']}_{r['i']}"
                allowed = prev_checked
                if not allowed:
                    st.session_state[bought_key] = False

                row_cols = st.columns([0.5, 0.9, 1.2, 1.3, 1.6, 1.6])
                checked = row_cols[0].checkbox(
                    "매수 완료", key=bought_key, label_visibility="collapsed", disabled=not allowed
                )
                bought = allowed and checked
                prev_checked = bought

                pnl_pct = (target_price - r["avg_price"]) / r["avg_price"] * 100 if r["avg_price"] > 0 else 0
                pnl_amt = (target_price - r["avg_price"]) * r["cum_qty"]

                # 고정 회색 대신 opacity로 흐리게 처리해서 라이트/다크 모드 모두에서 자연스럽게 보이도록 함
                text_style = "color:#00E5A0; font-weight:700;" if bought else "opacity:0.45;"
                row_cols[1].markdown(f"<span style='{text_style}'>{r['i'] + 1}회차{' ✓' if bought else ''}</span>", unsafe_allow_html=True)
                row_cols[2].markdown(f"<span style='{text_style}'>{fmt_price(r['price'], currency)}</span>", unsafe_allow_html=True)
                row_cols[3].markdown(f"<span style='{text_style}'>{fmt_price(r['avg_price'], currency)}</span>", unsafe_allow_html=True)
                row_cols[4].markdown(f"<span style='{text_style}'>{pnl_pct:+.1f}%</span>", unsafe_allow_html=True)
                row_cols[5].markdown(f"<span style='{text_style}'>{fmt_price(pnl_amt, currency)}</span>", unsafe_allow_html=True)
            st.caption("회차는 순서대로만 체크할 수 있어요 — 이전 회차를 체크해야 다음 회차가 활성화돼요.")

            bought_count = sum(1 for r in ladder if st.session_state.get(f"bought_{data['symbol']}_{r['i']}"))
            if bought_count:
                bought_rows = [r for r in ladder if st.session_state.get(f"bought_{data['symbol']}_{r['i']}")]
                last_bought = bought_rows[-1]
                st.divider()
                cur_pnl = (target_price - last_bought["avg_price"]) / last_bought["avg_price"] * 100 if last_bought["avg_price"] > 0 else 0
                st.markdown(
                    metric_row_html(
                        [
                            metric_card_html("매수 완료 회차", f"{bought_count} / {len(ladder)}회차", "green"),
                            metric_card_html("현재까지 평단가", fmt_price(last_bought["avg_price"], currency), "green"),
                            metric_card_html(
                                "목표가 달성시 예상 수익률", f"{cur_pnl:+.1f}%", "green" if cur_pnl >= 0 else "danger"
                            ),
                        ]
                    ),
                    unsafe_allow_html=True,
                )
else:
    st.info("종목을 검색해주세요.")
