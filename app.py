import streamlit as st
import pandas as pd
import random
from supabase import create_client, Client

# --- 1. 기본 설정 및 데이터베이스 연결 ---
st.set_page_config(page_title="주식 매매 게임", page_icon="📈", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- 2. 로그인 및 라우팅 로직 ---
if "role" not in st.session_state:
    st.title("📈 주식 매매 게임 로그인")
    
    role = st.radio("접속 유형", ["학생", "교수"], horizontal=True)
    class_name = st.selectbox("분반 선택", ["인하대", "숙대1", "숙대2"])
    
    if role == "학생":
        nickname = st.text_input("별명을 입력하세요 (예: 금융천재)")
        if st.button("학생 입장", type="primary"):
            if nickname:
                # 학생이 기존에 없으면 50달러/5주 지급하며 자동 가입
                res = supabase.table("stock_assets").select("*").eq("nickname", nickname).eq("class_name", class_name).execute()
                if not res.data:
                    supabase.table("stock_assets").insert({"nickname": nickname, "class_name": class_name, "cash": 50, "shares": 5}).execute()
                
                st.session_state.role = "student"
                st.session_state.nickname = nickname
                st.session_state.class_name = class_name
                st.rerun()
            else:
                st.error("별명을 입력해주세요!")
                
    else: # 교수 로그인
        pw = st.text_input("비밀번호", type="password")
        if st.button("교수 통제소 입장", type="primary"):
            if pw == "3383":
                st.session_state.role = "professor"
                st.session_state.class_name = class_name
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    st.stop()

# --- 3. 공통 변수 로드 ---
my_class = st.session_state.class_name
status_res = supabase.table("stock_status").select("*").eq("class_name", my_class).execute()
status_data = status_res.data[0]

current_round = status_data['current_round']
fair_value = status_data['fair_value']
is_started = status_data['is_started']

# 상단 공통 정보 및 로그아웃
col_title, col_logout = st.columns([8, 2])
with col_title:
    st.markdown(f"### 🏫 [{my_class}] 분반")
with col_logout:
    if st.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

st.write("---")

# ==========================================
# 👨‍🎓 학생용 화면
# ==========================================
if st.session_state.role == "student":
    me = st.session_state.nickname
    
    if not is_started:
        st.warning("⏳ 교수님이 게임을 시작할 때까지 대기해 주세요.")
        if st.button("상태 새로고침", type="primary"):
            st.rerun()
        st.stop()
        
    if current_round > 10:
        st.title("🏆 게임 종료!")
        st.write("모든 라운드가 끝났습니다. 교실 화면의 최종 결과를 확인하세요.")
        asset_res = supabase.table("stock_assets").select("*").eq("nickname", me).eq("class_name", my_class).execute()
        final_cash = asset_res.data[0]['cash']
        st.success(f"당신의 최종 수익: ${final_cash}")
        st.stop()

    st.info(f"**현재 진행 중:** {current_round} 라운드 (수학적 적정 가치: {fair_value}달러)")
    
    # 내 자산 불러오기
    asset_res = supabase.table("stock_assets").select("*").eq("nickname", me).eq("class_name", my_class).execute()
    cash = asset_res.data[0]['cash']
    shares = asset_res.data[0]['shares']
    
    st.success(f"환영합니다, **{me}** 펀드매니저님!")
    col1, col2 = st.columns(2)
    col1.metric("보유 현금", f"${cash}")
    col2.metric("보유 주식", f"{shares}주")
    
    st.subheader("📝 주문 입력")
    with st.form("order_form"):
        order_type = st.radio("주문 종류", ["매수 (살래)", "매도 (팔래)"], horizontal=True)
        price = st.number_input("희망 가격 (달러)", min_value=1, max_value=50, step=1)
        quantity = st.number_input("수량 (주)", min_value=1, max_value=50, step=1)
        submitted = st.form_submit_button("주문 전송")
        
        if submitted:
            # 중복 주문 확인 (한 라운드에 한 번만)
            check_order = supabase.table("stock_orders").select("*").eq("nickname", me).eq("class_name", my_class).eq("round", current_round).execute()
            if check_order.data:
                st.error("이번 라운드에 이미 주문을 제출했습니다!")
            elif order_type == "매수 (살래)" and (price * quantity) > cash:
                st.error(f"보유 현금이 부족합니다! (필요 현금: ${price * quantity})")
            elif order_type == "매도 (팔래)" and quantity > shares:
                st.error(f"보유 주식이 부족합니다! (현재 보유: {shares}주)")
            else:
                clean_type = "매수" if "매수" in order_type else "매도"
                supabase.table("stock_orders").insert({
                    "class_name": my_class, "round": current_round, "nickname": me, "order_type": clean_type, "price": price, "quantity": quantity
                }).execute()
                st.success("✅ 주문이 접수되었습니다! 교수님이 체결할 때까지 기다려주세요.")
                
    st.write("---")
    if st.button("화면 새로고침 (자산 확인)"):
        st.rerun()

# ==========================================
# 👨‍🏫 교수용 통제소 화면
# ==========================================
else:
    if current_round > 10:
        st.title("🏆 최종 랭킹보드")
        all_assets = supabase.table("stock_assets").select("*").eq("class_name", my_class).execute()
        df_rank = pd.DataFrame(all_assets.data)
        if not df_rank.empty:
            df_rank = df_rank.sort_values(by='cash', ascending=False).reset_index(drop=True)
            df_rank.index = df_rank.index + 1
            df_rank = df_rank[['nickname', 'cash', 'shares']]
            df_rank.columns = ['별명', '최종 수익(달러)', '남은 주식(주)']
            st.dataframe(df_rank, use_container_width=True)
            
        if st.button("🔄 이 분반 게임 초기화", type="secondary"):
            supabase.table("stock_status").update({"current_round": 1, "fair_value": 10, "is_started": False}).eq("class_name", my_class).execute()
            supabase.table("stock_assets").delete().eq("class_name", my_class).execute()
            supabase.table("stock_orders").delete().eq("class_name", my_class).execute()
            st.rerun()
        st.stop()

    st.title("👨‍🏫 교수 통제소")
    
    # 1. 현황판 및 새로고침
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    with col_stat1:
        if st.button("🔄 현황 새로고침", type="primary"):
            st.rerun()
    with col_stat2:
        students_res = supabase.table("stock_assets").select("nickname").eq("class_name", my_class).execute()
        st.info(f"**로그인한 학생 수:** {len(students_res.data)}명")
    with col_stat3:
        orders_res = supabase.table("stock_orders").select("nickname").eq("class_name", my_class).eq("round", current_round).execute()
        st.success(f"**주문 완료 학생 수:** {len(orders_res.data)}명")

    st.write("---")
    st.info(f"**진행 상황:** {current_round} 라운드 / **적정 가치:** {fair_value}달러")
    
    if not is_started:
        if st.button("🚀 1. 게임 시작 (학생 대기 해제)", use_container_width=True):
            supabase.table("stock_status").update({"is_started": True}).eq("class_name", my_class).execute()
            st.rerun()
        st.stop()

    # 주문 데이터 가져오기
    current_orders_res = supabase.table("stock_orders").select("*").eq("class_name", my_class).eq("round", current_round).execute()
    df_orders = pd.DataFrame(current_orders_res.data)

    col_b, col_s = st.columns(2)
    with col_b:
        st.subheader("🔴 매수 주문")
        if not df_orders.empty: st.dataframe(df_orders[df_orders['order_type'] == '매수'])
    with col_s:
        st.subheader("🔵 매도 주문")
        if not df_orders.empty: st.dataframe(df_orders[df_orders['order_type'] == '매도'])

    st.write("---")
    col_btn1, col_btn2, col_btn3 = st.columns(3)

    # [1. 거래 체결]
    with col_btn1:
        if st.button("🚨 2. 단일가 거래 체결", type="primary", use_container_width=True):
            if df_orders.empty:
                st.warning("접수된 주문이 없습니다.")
            else:
                buys = df_orders[df_orders['order_type'] == '매수']
                sells = df_orders[df_orders['order_type'] == '매도']
                
                all_prices = sorted(df_orders['price'].unique())
                best_price, max_volume = 0, 0
                
                for p in all_prices:
                    demand = buys[buys['price'] >= p]['quantity'].sum()
                    supply = sells[sells['price'] <= p]['quantity'].sum()
                    trade_vol = min(demand, supply)
                    if trade_vol > max_volume:
                        max_volume = trade_vol
                        best_price = p
                        
                if max_volume > 0:
                    # 모든 학생 자산 불러오기
                    assets_res = supabase.table("stock_assets").select("*").eq("class_name", my_class).execute()
                    assets_dict = {a['nickname']: a for a in assets_res.data}
                    
                    buys_sorted = buys.sort_values(by='price', ascending=False)
                    buy_left = max_volume
                    for _, row in buys_sorted.iterrows():
                        if buy_left <= 0: break
                        if row['price'] >= best_price:
                            fill = min(row['quantity'], buy_left)
                            if row['nickname'] in assets_dict:
                                assets_dict[row['nickname']]['cash'] -= fill * best_price
                                assets_dict[row['nickname']]['shares'] += fill
                            buy_left -= fill
                            
                    sells_sorted = sells.sort_values(by='price', ascending=True)
                    sell_left = max_volume
                    for _, row in sells_sorted.iterrows():
                        if sell_left <= 0: break
                        if row['price'] <= best_price:
                            fill = min(row['quantity'], sell_left)
                            if row['nickname'] in assets_dict:
                                assets_dict[row['nickname']]['cash'] += fill * best_price
                                assets_dict[row['nickname']]['shares'] -= fill
                            sell_left -= fill

                    # 수파베이스에 체결 결과 업데이트 (반복문)
                    for nick, data in assets_dict.items():
                        supabase.table("stock_assets").update({"cash": data['cash'], "shares": data['shares']}).eq("nickname", nick).eq("class_name", my_class).execute()
                        
                    st.success(f"🎉 체결 완료! 단일가: {best_price}달러 / 거래량: {max_volume}주")
                else:
                    st.error("조건이 맞지 않아 거래가 없습니다.")

    # [2. 배당금 추첨]
    with col_btn2:
        if st.button("🎰 3. 배당금 추첨", type="primary", use_container_width=True):
            dividend = random.choice([0, 2])
            if dividend == 2:
                st.balloons()
                st.success("🎉 주당 2달러 배당금 당첨!")
                # 주식을 가진 학생의 현금 증가
                assets_res = supabase.table("stock_assets").select("*").eq("class_name", my_class).execute()
                for data in assets_res.data:
                    if data['shares'] > 0:
                        new_cash = data['cash'] + (data['shares'] * 2)
                        supabase.table("stock_assets").update({"cash": new_cash}).eq("nickname", data['nickname']).eq("class_name", my_class).execute()
            else:
                st.error("💥 꽝입니다!")

    # [3. 다음 라운드]
    with col_btn3:
        btn_label = "🏁 4. 게임 종료" if current_round == 10 else "⏭️ 4. 다음 라운드 이동"
        if st.button(btn_label, type="primary", use_container_width=True):
            supabase.table("stock_status").update({
                "current_round": current_round + 1,
                "fair_value": fair_value - 1 if current_round < 10 else 0
            }).eq("class_name", my_class).execute()
            st.rerun()