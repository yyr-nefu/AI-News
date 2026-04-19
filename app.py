from flask import Flask, request, jsonify, make_response
import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
# 🔑 你的 Dify Chat API Key
DIFY_API_KEY = "app-XkgdeRjVy3HVr3W1kDF0Nsu3"

# 🧠 全局缓存（存今日资讯）
latest_summary = "今天暂无AI资讯"


# ================================
# 1️⃣ 接收 Dify Workflow 推送（存今日资讯）
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
# 2️⃣ 飞书消息入口（AI问答）
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

        # ✅ 防御：不是飞书结构
        if "event" not in data:
            return make_response(jsonify({
                "msg_type": "text",
                "content": {"text": "无效请求（非飞书格式）"}
            }), 200, {"ngrok-skip-browser-warning": "true"})

        # ================================
        # 👉 解析用户问题
        # ================================
        content = data.get("event", {}).get("message", {}).get("content", "")
        msg_json = json.loads(content) if content else {}
        question = msg_json.get("text", "")

        print("👤 用户问题：", question)

        # ================================
        # 👉 用户ID（防炸）
        # ================================
        user_id = data.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id", "test_user")

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

        answer = result.get("answer", "暂无回答")

        # ================================
        # 🔥 关键：返回 + 绕过 ngrok 拦截
        # ================================
        response = make_response(jsonify({
            "msg_type": "text",
            "content": {
                "text": answer
            }
        }))

        response.headers["ngrok-skip-browser-warning"] = "true"

        return response

    except Exception as e:
        print("❌ feishu 出错：", str(e))

        response = make_response(jsonify({
            "msg_type": "text",
            "content": {
                "text": f"出错了: {str(e)}"
            }
        }))

        response.headers["ngrok-skip-browser-warning"] = "true"

        return response


# ================================
# 启动服务
# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
