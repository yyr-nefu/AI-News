from flask import Flask, request, jsonify, Response
import requests
import json
import sys
import os

# ✅ 强制 stdout utf-8
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 🔑 Dify Chat Key（你已提供）
DIFY_API_KEY = "app-9oqjwy7dbC4Jd8XgzEjNzrqg"

# 🔥 飞书凭证（放 Render 环境变量）
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")

# 🧠 今日资讯缓存
latest_summary = "今天暂无AI资讯"


# ================================
# 0️⃣ 根路径
# ================================
@app.route("/", methods=["GET"])
def index():
    return "AI News Bot is running"


# ================================
# 1️⃣ 接收 Dify Workflow 推送
# ================================
@app.route("/update_news", methods=["POST"])
def update_news():
    global latest_summary

    try:
        data = request.get_json(force=True)
        print("📩 收到原始数据：", data)

        summary = data.get("summary", "")

        if summary:
            latest_summary = summary
            print("✅ 更新成功：", latest_summary)
        else:
            print("⚠️ 没拿到 summary")

        return jsonify({"status": "ok"})

    except Exception as e:
        print("❌ update_news 报错：", str(e))
        return jsonify({"error": str(e)})


# ================================
# 🔥 UTF-8响应（保留你的）
# ================================
def make_utf8_response(text):
    body = json.dumps({
        "msg_type": "text",
        "content": {
            "text": text
        }
    }, ensure_ascii=False)

    return Response(
        body,
        content_type="application/json; charset=utf-8"
    )


# ================================
# 🔥 获取 tenant_access_token
# ================================
def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    resp = requests.post(url, json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    })
    return resp.json().get("tenant_access_token")


# ================================
# 🔥 发送飞书消息
# ================================
def send_feishu_message(chat_id, text):
    token = get_tenant_access_token()

    url = "https://open.feishu.cn/open-apis/im/v1/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False)
    }

    resp = requests.post(url + "?receive_id_type=chat_id", headers=headers, json=body)
    print("📤 飞书发送结果：", resp.text)


# ================================
# 2️⃣ 飞书消息入口
# ================================
@app.route("/feishu", methods=["POST"])
def feishu():
    global latest_summary

    try:
        data = request.get_json(force=True)
        print("📩 飞书请求：", data)

        # ✅ challenge
        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})

        if "event" not in data:
            return jsonify({"code": 0})

        # ================================
        # 👉 解析用户问题
        # ================================
        content = data.get("event", {}).get("message", {}).get("content", "")
        msg_json = json.loads(content) if content else {}
        question = msg_json.get("text", "")

        # 🔥 去掉 @机器人
        question = question.replace("@_user_1", "").strip()

        print("👤 用户问题：", question)

        # 👉 用户ID
        user_id = data.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id", "test_user")

        # 👉 chat_id（发消息用）
        chat_id = data.get("event", {}).get("message", {}).get("chat_id")

        # ================================
        # 👉 调用 Dify
        # ================================
        resp = requests.post(
            "https://api.dify.ai/v1/chat-messages",
            headers={
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "inputs": {
                    "context": latest_summary
                },
                "query": question,
                "response_mode": "blocking",
                "user": user_id
            },
            timeout=20
        )

        result = resp.json()
        print("🤖 Dify返回：", result)

        # ✅ Key错误处理
        if result.get("code") == "unauthorized":
            answer = "❌ Dify Key 无效（必须用 Chat App 并发布）"
        else:
            answer = result.get("answer", "暂无回答")

        # 🔥 主动发消息（关键）
        send_feishu_message(chat_id, answer)

        # 🔥 飞书必须返回200
        return jsonify({"code": 0})

    except Exception as e:
        print("❌ feishu 出错：", str(e))
        return jsonify({"code": 0})


# ================================
# 🚀 Render 启动
# ================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
