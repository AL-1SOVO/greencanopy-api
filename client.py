import requests
import time

# 你的 FastAPI 后端地址
SERVER_URL = "http://127.0.0.1:8000/chat"

print("========================================")
print(" 🌱 智慧大棚 AI 终端 (CLI 客户端模式)")
print(" 提示：输入 'quit' 或 'exit' 退出系统")
print("========================================\n")

while True:
    # 1. 获取用户输入
    user_input = input("🧑‍🌾 你: ")
    
    # 退出逻辑
    if user_input.lower() in ['quit', 'exit']:
        print("👋 拜拜！系统已安全退出。")
        break
    if not user_input.strip():
        continue

    # 2. 准备发送给后端的数据
    # 注意：FastAPI 设定的是 Form(...)，所以这里用 data=payload（如果是 JSON，则用 json=payload）
    payload = {"message": user_input}

    print("   [客户端] 正在向服务器发送请求...")
    start_time = time.time()

    try:
        # 3. 发送 POST 请求 (相当于前端向后端“搭讪”)
        response = requests.post(SERVER_URL, data=payload)
        
        # 检查 HTTP 状态码，如果不是 200 (比如我们昨天写的 500 传感器掉线)，会触发 HTTPError
        response.raise_for_status() 
        
        # 4. 解析后端返回的 JSON 数据
        result = response.json()
        answer = result.get("answer", "未获取到回答")
        
        latency = round(time.time() - start_time, 2)
        print(f"🤖 AI (耗时 {latency}s): {answer}\n")
        
    except requests.exceptions.ConnectionError:
        print("❌ [本地网络错误] 无法连接到服务器。")
        print("   👉 提示：你是不是忘了在另一个终端启动 `uvicorn day35:app --reload`？\n")
        
    except requests.exceptions.HTTPError as e:
        # 5. 优雅处理我们昨天在后端写的异常拦截 (HTTPException)
        try:
            error_msg = response.json().get("detail", str(e))
        except ValueError:
            error_msg = response.text
        print(f"⚠️ [服务器报错 {response.status_code}]: {error_msg}\n")
        
    except Exception as e:
        print(f"❌ [未知错误]: {str(e)}\n")