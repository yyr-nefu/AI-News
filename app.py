from flask import Flask, request, jsonify, make_response
import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

DIFY_API_KEY = "app-XkgdeRjVy3HVr3W1kDF0Nsu3"

latest_summary = "今天暂无AI资讯"


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


@app.route("/feishu", methods=["POST"])
def feishu():
    global latest_summary

    try:
        data = request.get_json(force=True)
        print("📩 飞书请求：", data)

        # 飞书验证
        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})

        if "event" not in data:
            return make_utf8_response("无效请求（非飞书格式）")

        # 解析消息
        content = data.get("event", {}).get("message", {}).get("content", "")
        msg_json = json.loads(content) if content else {}
        question = msg_json.get("text", "")

        print("👤 用户问题：", question)

        user_id = data.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id", "test_user")

        # ✅ 改这里：Chatflow 要用 workflows/run
        resp = requests.post(
            "https://api.dify.ai/v1/workflows/run",
            headers={
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                # ✅ 改这里：query 要放进 inputs
                "inputs": {
                    "query": question,
                    "context": latest_summary
                },
                "response_mode": "blocking",
                "user": user_id
            },
            timeout=20
        )

        result = resp.json()
        print("🤖 Dify返回：", result)

        # ✅ 改这里：Chatflow 返回结构
        answer = result.get("data", {}).get("outputs", {}).get("text", "暂无回答")

        return make_utf8_response(answer)

    except Exception as e:
        print("❌ feishu 出错：", str(e))
        return make_utf8_response(f"出错了: {str(e)}")


# 🔥🔥🔥 核心函数（彻底解决中文乱码）
def make_utf8_response(text):
    response = make_response(json.dumps({
        "msg_type": "text",
        "content": {"text": text}
    }, ensure_ascii=False))

    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["ngrok-skip-browser-warning"] = "true"

    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
