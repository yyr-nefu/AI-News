from flask import Flask, request, jsonify, Response
import requests
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

DIFY_API_KEY = "app-9oqjwy7dbC4Jd8XgzEjNzrqg"

# 🔥 必须从 Render 环境变量读取
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")

latest_summary = "今天暂无AI资讯"


@app.route("/", methods=["GET"])
def index():
    return "AI News Bot is running"


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


def make_utf8_response(text):
    body = json.dumps({
        "msg_type": "text",
        "content": {"text": text}
    }, ensure_ascii=False)

    return Response(body, content_type="application/json; charset=utf-8")


# ================================
# 🔥 获取 token（增强版）
# ================================
def get_tenant_access_token():
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 环境变量没配：FEISHU_APP_ID / FEISHU_APP_SECRET")
        return None

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

    resp = requests.post(url, json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    })

    data = resp.json()
    print("🔑 token返回：", data)

    if data.get("code") != 0:
        print("❌ token获取失败：", data)
        return None

    return data.get("tenant_access_token")


# ================================
# 🔥 发消息（增强版）
# ================================
def send_feishu_message(chat_id, text):
    token = get_tenant_access_token()

    if not token:
        print("❌ 没拿到 token，停止发送")
        return

    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False)
    }

    resp = requests.post(url, headers=headers, json=body)

    print("📤 飞书发送结果：", resp.text)


@app.route("/feishu", methods=["POST"])
def feishu():
    global latest_summary

    try:
        data = request.get_json(force=True)
        print("📩 飞书请求：", data)

        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})

        if "event" not in data:
            return jsonify({"code": 0})

        content = data.get("event", {}).get("message", {}).get("content", "")
        msg_json = json.loads(content) if content else {}
        question = msg_json.get("text", "")

        question = question.replace("@_user_1", "").strip()
        print("👤 用户问题：", question)

        user_id = data.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id", "test_user")
        chat_id = data.get("event", {}).get("message", {}).get("chat_id")

        if not chat_id:
            print("❌ 没拿到 chat_id")
            return jsonify({"code": 0})

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

        if result.get("code") == "unauthorized":
            answer = "❌ Dify Key 无效"
        else:
            answer = result.get("answer", "暂无回答")

        send_feishu_message(chat_id, answer)

        return jsonify({"code": 0})

    except Exception as e:
        print("❌ feishu 出错：", str(e))
        return jsonify({"code": 0})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
