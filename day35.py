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

# 初始化大模型 (此處以智譜 GLM-4 為例)
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
        "description": "【核心工具】獲取大棚的即時環境數據。當用戶詢問『現在』溫度、濕度或沒提時間時，必須優先調用此工具。",
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
# 3. 傳統 API 路由 (加裝監控打印 + 強制開口指令)
# ==========================================
@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    print(f"\n========== 傳統路由 新對話開始 ==========")
    print(f"👉 收到用戶提問: {message}")
    
    sys_prompt = "你是一個專業的大棚助理。獲取數據後，必須用友善的自然語言回答用戶！絕對不能輸出空白！"
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=message)
    ]
    
    response = await llm_with_tools.ainvoke(messages)
    print(f"🤖 模型第一階段思考結果: 是否調用工具? -> {bool(response.tool_calls)}")
    
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
        
        messages.append(HumanMessage(
            content=f"系統提示：傳感器剛剛返回的數據是 {obs}。請立刻用自然語言把這個結果告訴用戶！"
        ))
        
        final_response = await llm_with_tools.ainvoke(messages)
        print(f"🤖 模型最終吐出的回答: '{final_response.content}'")
        return {"answer": final_response.content}
        
    print(f"🤖 模型未調用工具，直接回答: '{response.content}'")
    return {"answer": response.content}

# ==========================================
# 4. 終極流式 API 路由 (加裝監控、強勢提示詞與強制開口)
# ==========================================
# ==========================================
# 4. 终极流式 API 路由 (加装监控、强势提示词、强制开口与【刹车机制】)
# ==========================================
@app.post("/chat_stream")
async def chat_stream_endpoint(
    message: str = Form(...),
    file: UploadFile = File(None)  # 接收前端传来的可选文件
):
    # --- 1. 启动监控日志 ---
    print(f"\n========== 🌐 [流式路由] 新对话开始 ==========")
    print(f"👉 用户提问: {message}")
    print(f"📎 是否携带附件: {'是 (' + file.filename + ')' if file else '否'}")

    # --- 2. 处理上传的文件 ---
    # --- 2. 处理上传的文件 ---
    file_context = ""
    if file:
        try:
            content = await file.read()
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
            # 💡 终极修复：干掉 .head(10)，直接把整张表或前100行丢给它！
            # 如果你的表不太大，可以直接用 df.to_markdown()
            # 如果表有点大怕超过限制，可以用 df.head(200).to_markdown()
            file_context = f"""
            \n\n【系统提示：用户本次上传了附件 {file.filename}】
            包含字段: {', '.join(df.columns)}
            完整数据内容如下:
            {df.to_markdown()}
            """
            print("📎 附件解析成功，已完整加入上下文。")
        except Exception as e:
            print(f"❌ 附件读取失败: {e}")
            file_context = f"\n\n【系统提示：读取附件失败，错误信息 {e}】"

    # --- 3. 定义流式生成器 (水管) ---
    async def event_generator():
        # 💡 神级装备 1：强势提示词
        sys_prompt = """你是一个专业的农业大棚AI中控大脑。
        【最高行为准则】：
        1. 若用户询问「现在、当前」的温度/湿度，你【必须】立刻调用工具获取，严禁反问用户！
        2. 若用户询问历史资料或表格内容，请分析下方的【附件】。
        3. 拿到数据后，必须用人类语言给出完整的回答。"""
        
        if file_context:
            sys_prompt += file_context
            
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=message)
        ]
        
        try:
            # ====================================================
            # 💡 【你问的刹车机制就是放在这里！】
            # 第一阶段：拦截与常规思考
            # 判断用户是否在问历史/文件 (增加了简体和繁体的常见关键词)
            is_asking_history = any(kw in message for kw in ["文件", "档案", "历史", "表格", "日前", "号", "这几天", "数据"])
            
            # 如果有上传文件，且用户明确提到要看文件/历史，直接阉割工具，强迫它看文件
            if file_context and is_asking_history:
                print("🛡️ 侦测到用户询问历史文件，主动锁定传感器工具，强迫 AI 读取表格！")
                ai_msg = await llm.ainvoke(messages)  # 👈 注意：这里用的是纯 llm，没有工具！
            else:
                # 正常情况下（问现在温度），依然允许调用工具
                ai_msg = await llm_with_tools.ainvoke(messages)
            # ====================================================
            
            messages.append(ai_msg)
            
            # 提取工具调用列表 (安全提取，防止纯 llm 返回时报错)
            tool_calls = getattr(ai_msg, 'tool_calls', [])
            print(f"🤖 AI工具调用决策: {tool_calls}")
            
            # 第二阶段：工具调用处理
            if tool_calls:
                yield "📡 正在调取 5G 传感器即时数据...\n\n"
                
                tool_call = tool_calls[0]
                obs = await get_sensor_data(
                    tool_call["args"].get("location", "一号大棚"), 
                    tool_call["args"].get("sensor_type", "temperature")
                )
                print(f"📡 传感器成功抓取数据: {obs}")
                
                # 💡 神级装备 2：带有身份证的 ToolMessage
                messages.append(ToolMessage(
                    content=str(obs), 
                    tool_call_id=tool_call["id"], 
                    name=tool_call["name"]
                ))
                
                # 💡 神级装备 3：致命一击，强迫开口！
                messages.append(HumanMessage(
                    content=f"系统提示：传感器刚刚返回的数据是 {obs}。请立刻结合用户的问题，用自然语言把结果告诉用户！绝对不要输出空白！"
                ))
                
                # 拿到数据后，开启流式水管输出最终总结
                async for chunk in llm_with_tools.astream(messages):
                    if chunk.content:
                        yield chunk.content
            else:
                # 如果没有调用工具 (普通聊天或正在分析表格)，直接流式输出内容
                print("🤖 AI决定不使用工具，直接回答。")
                for char in ai_msg.content:
                    yield char
                    await asyncio.sleep(0.01) # 模拟打字延迟
                    
        except Exception as e:
            print(f"❌ 后端运行错误: {e}")
            yield f"\n\n❌ 系统发生错误：{str(e)}"

    # --- 4. 返回 SSE 流式响应 ---
    return StreamingResponse(event_generator(), media_type="text/event-stream")