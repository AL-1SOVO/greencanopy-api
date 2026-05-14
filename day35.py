import os
import random
import asyncio
import io
import pandas as pd
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from langchain_community.chat_models import ChatZhipuAI
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage

# ==========================================
# 1. 基礎配置與模型初始化
# ==========================================
load_dotenv()
api_key = os.getenv("ZHIPUAI_API_KEY")

# 初始化大模型 (此處以智譜 GLM-4 為例，如果你用其他模型請自行替換)
llm = ChatZhipuAI(model="glm-4-flash", api_key=api_key, temperature=0.1)

app = FastAPI(title="農業智慧中控：全棧 Web Agent 後端大腦")

# CORS 配置 (允許前端 Streamlit 跨域請求)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 2. 定義 Agent 工具 (物聯網傳感器)
# ==========================================
async def get_sensor_data(location: str, sensor_type: str) -> str:
    """模擬從 5G 網關獲取真實傳感器數據"""
    await asyncio.sleep(1.5)  # 模擬網路延遲
    if sensor_type == "temperature" or sensor_type == "leaf_temperature":
        return f"{round(random.uniform(20.0, 32.0), 1)}°C"
    elif sensor_type == "humidity":
        return f"{random.randint(40, 85)}%"
    return "數據暫缺"

tools = [{
    "type": "function",
    "function": {
        "name": "get_sensor_data",
        "description": "獲取智慧農業傳感器的即時數據 (如溫度、葉溫、濕度)",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "大棚位置，例如：一號大棚"},
                "sensor_type": {"type": "string", "enum": ["temperature", "leaf_temperature", "humidity"], "description": "傳感器類型"}
            },
            "required": ["location", "sensor_type"]
        }
    }
}]

# 將工具綁定到大模型
llm_with_tools = llm.bind_tools(tools)

# ==========================================
# 3. 傳統 API 路由 (保留給舊版客戶端使用)
# ==========================================
@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    messages = [HumanMessage(content=message)]
    response = await llm_with_tools.ainvoke(messages)
    return {"answer": response.content}

# ==========================================
# 4. 終極流式 API 路由 (支援多模態檔案與 Agent 工具)
# ==========================================
@app.post("/chat_stream")
async def chat_stream_endpoint(
    message: str = Form(...),
    file: UploadFile = File(None)  # 接收前端傳來的可選檔案
):
    # --- A. 處理上傳的文件 ---
    file_context = ""
    if file:
        try:
            content = await file.read()
            # 💡 防禦亂碼：強制使用 utf-8-sig 解碼 CSV
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
            file_context = f"""
            \n\n[系統提示：用戶上傳了一份名為 {file.filename} 的數據表]
            數據預覽 (前5行):
            {df.head().to_markdown()}
            
            數據欄位包含: {', '.join(df.columns)}
            """
        except Exception as e:
            print(f"文件讀取失敗: {e}")
            file_context = f"\n\n[系統提示：讀取文件失敗，錯誤訊息 {e}]"

    # --- B. 定義流式生成器 (水管) ---
    async def event_generator():
        # 💡 動態組裝系統提示詞 (解決 Agent 工具依賴症)
        sys_prompt = "你是一個專業的農業數據分析師兼大棚助理。回答請保持友善且專業。"
        if file_context:
            sys_prompt += file_context + "根据用户需求决定调用用户上传的文件或者传感器来回答用户问题"
        
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=message)
        ]
        
        try:
            # 第一階段：常規思考 (判斷是否需要調用工具，不開啟流式)
            ai_msg = await llm_with_tools.ainvoke(messages)
            messages.append(ai_msg)
            
            # 第二階段：工具調用攔截與處理
            if ai_msg.tool_calls:
                # 提示用戶系統正在後台運作
                yield "📡 正在調取 5G 傳感器即時數據...\n\n"
                
                tool_call = ai_msg.tool_calls[0]
                obs = await get_sensor_data(
                    tool_call["args"].get("location", "大棚"), 
                    tool_call["args"].get("sensor_type", "temperature")
                )
                messages.append(ToolMessage(content=obs, tool_call_id=tool_call["id"]))
                
                # 拿到數據後，開啟流式水管輸出最終總結
                async for chunk in llm_with_tools.astream(messages):
                    if chunk.content:
                        yield chunk.content
            else:
                # 如果沒有調用工具 (普通聊天或正在分析表格)，直接流式輸出內容
                for char in ai_msg.content:
                    yield char
                    await asyncio.sleep(0.01) # 模擬一點點打字延遲，讓畫面更平滑
                    
        except Exception as e:
            print(f"❌ 後端運行錯誤: {e}")
            yield f"\n\n❌ 系統發生錯誤：{str(e)}"

    # --- C. 返回 SSE 流式響應 ---
    return StreamingResponse(event_generator(), media_type="text/event-stream")