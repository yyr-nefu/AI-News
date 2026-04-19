from flask import Flask, request, jsonify, make_response
import requests
import json
import sys
import os

# ✅ 防止中文报错
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 🔑 换成你「Chat App」的 Key（必须重新拿）
DIFY_API_KEY = "app-这里换成你新的key"

# 🧠 今日资讯缓存
latest_summary = "今天暂无AI资讯"


# ================================
# 0️⃣ 根路径（防止 Render 404）
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
# 2️⃣ 飞书消息入口
# ================================
@app.route("/feishu", methods=["POST"])
def feishu():
    global latest_summary

    try:
        data = request.get_json(force=True)
        print("📩 飞书请求：", data)

        # ✅ 飞书 challenge 验证
        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})

        # ❌ 非飞书结构
        if "event" not in data:
            return make_response(jsonify({
                "msg_type": "text",
                "content": {"text": "无效请求"}
            }), 200)

        # ================================
        # 👉 解析用户问题
        # ================================
        content = data.get("event", {}).get("message", {}).get("content", "")
        msg_json = json.loads(content) if content else {}
        question = msg_json.get("text", "")

        print("👤 用户问题：", question)

        # 👉 用户ID
        user_id = data.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id", "test_user")

        # ================================
        # 👉 调用 Dify Chat
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

        # ❌ Key错误处理（你之前卡这里）
        if result.get("code") == "unauthorized":
            answer = "❌ Dify Key 无效，请检查是否使用 Chat App 的 API Key 并已发布"
        else:
            answer = result.get("answer", "暂无回答")

        # ================================
        # 👉 返回飞书
        # ================================
        response = make_response(jsonify({
            "msg_type": "text",
            "content": {
                "text": answer
            }
        }))

        # ✅ 关键：防 ngrok/代理拦截
        response.headers["Content-Type"] = "application/json; charset=utf-8"

        return response

    except Exception as e:
        print("❌ feishu 出错：", str(e))

        return jsonify({
            "msg_type": "text",
            "content": {
                "text": f"出错了: {str(e)}"
            }
        })


# ================================
# 🚀 启动（适配 Render）
# ================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # ✅ Render 必须
    app.run(host="0.0.0.0", port=port)
