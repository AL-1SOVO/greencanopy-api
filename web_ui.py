import streamlit as st
import requests
from requests.exceptions import ConnectionError  # 🌟 導入專門處理連線錯誤的模組

API_URL = "http://127.0.0.1:8000/chat_stream"
st.set_page_config(page_title="智慧大棚 AI 中控", page_icon="🌱", layout="wide")

# ==========================================
# 1. 側邊欄設定與檔案掛載
# ==========================================
with st.sidebar:
    st.header("📎 數據分析中心")
    uploaded_file = st.file_uploader("上傳大棚歷史數據 (CSV)", type=["csv"])
    if uploaded_file:
        st.success(f"✅ 已掛載文件：{uploaded_file.name}")
        
    st.markdown("---")
    if st.button("🗑️ 清空歷史對話", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("🌱 智慧大棚 5G 助理 (高可用版)")

# 初始化狀態
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "您好！系統已就緒，請隨時發送指令或上傳數據。"}]

avatars = {"user": "🧑‍🌾", "assistant": "🤖"}

# 渲染歷史紀錄
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=avatars.get(msg["role"])):
        st.markdown(msg["content"])

# ==========================================
# 2. 對話與高可用防護邏輯
# ==========================================
if prompt := st.chat_input("請輸入指令..."):
    with st.chat_message("user", avatar=avatars["user"]):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant", avatar=avatars["assistant"]):
        def stream_data():
            try:
                # 打包檔案
                files_payload = None
                if uploaded_file is not None:
                    files_payload = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
                
                # 🌟 UX 升級 1：載入動畫 (Spinner)
                # 這個動畫只會在「等待第一滴水流過來」的期間顯示，一旦開始流式輸出就會自動消失
                with st.spinner("📡 正在連線至 5G 中控大腦，請稍候..."):
                    response = requests.post("http://host.docker.internal:8000/chat_stream", data={"message": prompt}, files=files_payload, stream=True)
                    response.raise_for_status() # 檢查是否有 500 等伺服器內部錯誤

                # 🌟 開始接收流式數據
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        yield chunk

            # 🌟 UX 升級 2：優雅的錯誤攔截 (防禦後端未啟動)
            except ConnectionError:
                yield "💤 **系統警報：中控大腦似乎睡著了！**\n\n請確認您的 FastAPI 後端伺服器 (`uvicorn day35:app --reload`) 是否已經啟動。我現在無法為您獲取大棚數據。"
            
            # 🌟 攔截其他未知錯誤
            except Exception as e:
                yield f"❌ **連線發生異常：** {e}\n\n請聯絡系統管理員進行排查。"

        # 呼叫流式輸出並存入記憶
        full_response = st.write_stream(stream_data())
        st.session_state.messages.append({"role": "assistant", "content": full_response})