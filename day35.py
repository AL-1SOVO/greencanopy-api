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
# 3. 傳統 API 路由 (已修復：支援工具調用 + 系統提示 + 身份證)
# ==========================================
@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    # 💡 修復 1：加上系統提示，讓它知道自己是誰
    sys_prompt = "你是一個專業的農業數據分析師兼大棚助理。請主動使用工具獲取傳感器數據來回答問題。"
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=message)
    ]
    
    # 第一階段：讓大模型思考
    response = await llm_with_tools.ainvoke(messages)
    
    # 如果模型決定使用工具 (比如獲取溫度)
    if response.tool_calls:
        # 把模型的請求加入對話記錄
        messages.append(response)
        
        # 提取工具參數並執行你的模擬函數
        tool_call = response.tool_calls[0]
        obs = await get_sensor_data(
            tool_call["args"].get("location", "一號大棚"), 
            tool_call["args"].get("sensor_type", "temperature")
        )
        
        # 💡 修復 2：必須加上 name=tool_call["name"] 身份證，否則智譜會報錯或罷工！
        messages.append(ToolMessage(
            content=str(obs), 
            tool_call_id=tool_call["id"], 
            name=tool_call["name"]
        ))
        
        # 第二階段：讓模型根據傳感器數據給出最終回答
        final_response = await llm_with_tools.ainvoke(messages)
        return {"answer": final_response.content}
        
    # 如果模型不打算用工具 (比如普通的閒聊)，直接返回內容
    return {"answer": response.content}

# ==========================================
# 4. 終極流式 API 路由 (支援多模態檔案與 Agent 工具)
# ==========================================
# ==========================================
# 3. 傳統 API 路由 (加裝監控打印 + 強制開口指令)
# ==========================================
@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    print(f"\n========== 新對話開始 ==========")
    print(f"👉 收到用戶提問: {message}")
    
    sys_prompt = "你是一個專業的大棚助理。獲取數據後，必須用友善的自然語言回答用戶！絕對不能輸出空白！"
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=message)
    ]
    
    # 第一階段：讓大模型思考
    response = await llm_with_tools.ainvoke(messages)
    print(f"🤖 模型第一階段思考結果: 是否調用工具? -> {bool(response.tool_calls)}")
    
    # 如果模型決定使用工具
    if response.tool_calls:
        messages.append(response)
        
        tool_call = response.tool_calls[0]
        obs = await get_sensor_data(
            tool_call["args"].get("location", "一號大棚"), 
            tool_call["args"].get("sensor_type", "temperature")
        )
        print(f"📡 傳感器成功拿到數據: {obs}")
        
        messages.append(ToolMessage(
            content=str(obs), 
            tool_call_id=tool_call["id"], 
            name=tool_call["name"]
        ))
        
        # ⚡ 致命一擊：強迫大模型開口講話！
        messages.append(HumanMessage(
            content=f"系統提示：傳感器剛剛返回的數據是 {obs}。請立刻用自然語言把這個結果告訴用戶！"
        ))
        
        # 第二階段：讓模型給出最終回答
        final_response = await llm_with_tools.ainvoke(messages)
        print(f"🤖 模型最終吐出的回答: '{final_response.content}'")
        return {"answer": final_response.content}
        
    # 如果沒用工具，直接回答
    print(f"🤖 模型未調用工具，直接回答: '{response.content}'")
    return {"answer": response.content}

    # --- B. 定義流式生成器 (水管) ---
    async def event_generator():
        sys_prompt = "你是一個專業的農業數據分析師兼大棚助理。回答請保持友善且專業。"
        if file_context:
            sys_prompt += file_context + "根据用户需求决定调用用户上传的文件或者传感器来回答用户问题"
        
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=message)
        ]
        
        try:
            ai_msg = await llm_with_tools.ainvoke(messages)
            messages.append(ai_msg)
            
            if ai_msg.tool_calls:
                yield "📡 正在調取 5G 傳感器即時數據...\n\n"
                
                tool_call = ai_msg.tool_calls[0]
                obs = await get_sensor_data(
                    tool_call["args"].get("location", "大棚"), 
                    tool_call["args"].get("sensor_type", "temperature")
                )
                
                # 💡 修復 3：流式路由這裡也要補上 name=tool_call["name"]
                messages.append(ToolMessage(
                    content=str(obs), 
                    tool_call_id=tool_call["id"], 
                    name=tool_call["name"]
                ))
                
                async for chunk in llm_with_tools.astream(messages):
                    if chunk.content:
                        yield chunk.content
            else:
                for char in ai_msg.content:
                    yield char
                    await asyncio.sleep(0.01)
                    
        except Exception as e:
            print(f"❌ 後端運行錯誤: {e}")
            yield f"\n\n❌ 系統發生錯誤：{str(e)}"

    # --- C. 返回 SSE 流式響應 ---
    return StreamingResponse(event_generator(), media_type="text/event-stream")