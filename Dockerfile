# 1. 指定基底映像檔 (我們選用輕量版的 Python 3.10)
FROM python:3.10-slim

# 2. 設定容器內的工作目錄 (相當於在容器裡 mkdir /app 並且 cd /app)
WORKDIR /app

# 3. 先把依賴清單複製進容器
COPY requirements.txt .

# 4. 在容器內執行 pip 安裝依賴 (利用 Docker 緩存機制加速未來構建)
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 5. 把本機專案裡的所有檔案，複製到容器的 /app 目錄下
COPY . .

# 6. 宣告這個容器對外開放 8000 埠
EXPOSE 8000

# 7. 容器啟動時執行的終極指令 
# 🚨 關鍵陷阱：必須加上 --host 0.0.0.0，否則容器外部連不進來！
CMD ["uvicorn", "day35:app", "--host", "0.0.0.0", "--port", "8000"]