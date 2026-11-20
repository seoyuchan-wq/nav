
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
from dotenv import load_dotenv
import requests
import os

# API 키 불러오기
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
KAKAO_API_KEY = os.getenv("KAKAO_REST_API_KEY")

app = Flask(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

# 웹페이지
HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>음성 내비게이션</title>

<style>
body {
    font-family: Arial, sans-serif;
    background: #f1f4f9;
    text-align: center;
    padding: 30px 15px;
}

.container {
    max-width: 480px;
    margin: 30px auto;
    padding: 30px 20px;
    background: white;
    border-radius: 20px;
    box-shadow: 0 5px 20px #0002;
}

#speakBtn {
    width: 150px;
    height: 150px;
    border-radius: 50%;
    border: none;
    background: #2864e8;
    color: white;
    font-size: 24px;
    cursor: pointer;
}

#speakBtn:disabled {
    background: gray;
}

#status {
    color: #2864e8;
    font-weight: bold;
    margin: 25px;
}

.card {
    padding: 15px;
    margin-top: 15px;
    border: 1px solid #ddd;
    border-radius: 12px;
    text-align: left;
}

.address {
    color: #666;
    font-size: 14px;
}

.tmapBtn {
    width: 100%;
    padding: 14px;
    margin-top: 10px;
    background: #03a9f4;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    cursor: pointer;
}
</style>
</head>

<body>
<div class="container">

    <h1>🚗 음성 내비게이션</h1>

    <p>목적지를 음성으로 말씀해주세요.</p>

    <button id="speakBtn">🎤 말하기</button>

    <p id="status">말하기 버튼을 눌러주세요.</p>

    <div>
        <h3>음성 인식 결과</h3>
        <p id="speechResult">입력 대기 중</p>
    </div>

    <div id="results"></div>

</div>

<script>
const speakBtn = document.getElementById("speakBtn");
const statusText = document.getElementById("status");
const speechResult = document.getElementById("speechResult");
const results = document.getElementById("results");

const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

if (!SpeechRecognition) {
    statusText.textContent =
        "음성인식을 지원하지 않습니다. Chrome을 사용해주세요.";
    speakBtn.disabled = true;
} else {

    const recognition = new SpeechRecognition();

    recognition.lang = "ko-KR";
    recognition.continuous = false;
    recognition.interimResults = false;

    speakBtn.onclick = () => {
        speechResult.textContent = "";
        results.innerHTML = "";

        statusText.textContent = "목적지를 말씀해주세요.";
        speakBtn.disabled = true;

        try {
            recognition.start();
        } catch (e) {
            statusText.textContent = "다시 시도해주세요.";
            speakBtn.disabled = false;
        }
    };

    recognition.onresult = async (event) => {
        const text = event.results[0][0].transcript;

        speechResult.textContent = text;
        statusText.textContent = "목적지를 검색 중입니다.";

        await searchDestination(text);
    };

    recognition.onerror = () => {
        statusText.textContent =
            "음성인식에 실패했습니다. 다시 말씀해주세요.";

        speakBtn.disabled = false;
    };

    recognition.onend = () => {
        speakBtn.disabled = false;
    };
}

async function searchDestination(text) {
    try {
        const response = await fetch("/search", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                speechText: text
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            statusText.textContent =
                data.message || "검색에 실패했습니다.";
            return;
        }

        statusText.textContent =
            data.destination + " 검색 결과입니다.";

        showPlaces(data.places);

    } catch (error) {
        statusText.textContent =
            "서버 오류가 발생했습니다.";
    } finally {
        speakBtn.disabled = false;
    }
}

function showPlaces(places) {
    results.innerHTML = "";

    places.forEach(place => {
        const card = document.createElement("div");
        card.className = "card";

        const title = document.createElement("h3");
        title.textContent = place.name;

        const address = document.createElement("p");
        address.className = "address";
        address.textContent = place.address || "주소 정보 없음";

        const button = document.createElement("button");
        button.className = "tmapBtn";
        button.textContent = "TMAP 가기";

        button.onclick = () => {
            const url =
                "tmap://route?goalname=" +
                encodeURIComponent(place.name) +
                "&goalx=" + place.longitude +
                "&goaly=" + place.latitude;

            window.location.href = url;
        };

        card.append(title, address, button);
        results.appendChild(card);
    });
}
</script>
</body>
</html>
"""

# 메인 화면
@app.route("/")
def home():
    return render_template_string(HTML)


# 목적지 검색
@app.route("/search", methods=["POST"])
def search():

    try:
        speech_text = request.json.get("speechText", "").strip()

        if not speech_text:
            return jsonify({
                "success": False,
                "message": "다시 말씀해주세요."
            }), 400

        if not OPENAI_API_KEY or not KAKAO_API_KEY:
            return jsonify({
                "success": False,
                "message": "API 키를 확인해주세요."
            }), 500

        # 1. GPT 목적지 추출
        response = client.responses.create(
            model="gpt-4.1-mini",
            instructions="""
            사용자의 문장에서 내비게이션 목적지만 추출하세요.
            예: 서울역으로 가자 -> 서울역
            목적지를 알 수 없으면 null을 반환하세요.
            """,
            input=speech_text,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "destination",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "destination": {
                                "type": ["string", "null"]
                            }
                        },
                        "required": ["destination"],
                        "additionalProperties": False
                    }
                }
            }
        )

        import json
        result = json.loads(response.output_text)

        destination = result["destination"]

        if not destination:
            return jsonify({
                "success": False,
                "message": "목적지를 확인할 수 없습니다. 다시 말씀해주세요."
            })

        # 2. Kakao Local API 검색
        kakao_url = (
            "https://dapi.kakao.com/v2/local/search/keyword.json"
        )

        headers = {
            "Authorization": f"KakaoAK {KAKAO_API_KEY}"
        }

        params = {
            "query": destination,
            "size": 5
        }

        kakao_response = requests.get(
            kakao_url,
            headers=headers,
            params=params,
            timeout=10
        )

        kakao_response.raise_for_status()

        kakao_data = kakao_response.json()

        documents = kakao_data.get("documents", [])

        if not documents:
            return jsonify({
                "success": False,
                "message": "검색 결과가 없습니다. 다시 말씀해주세요."
            })

        # 3. 검색 결과 정리
        places = []

        for p in documents:
            places.append({
                "name": p["place_name"],
                "address": (
                    p["road_address_name"]
                    or p["address_name"]
                ),
                "latitude": float(p["y"]),
                "longitude": float(p["x"])
            })

        return jsonify({
            "success": True,
            "destination": destination,
            "places": places
        })

    except Exception as e:
        print("오류:", str(e))

        return jsonify({
            "success": False,
            "message": "검색 오류가 발생했습니다. 다시 시도해주세요."
        }), 500


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
