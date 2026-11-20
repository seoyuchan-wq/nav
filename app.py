
import os
import json
import logging
import requests

from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
from dotenv import load_dotenv

# =====================================
# 1. 기본 설정
# =====================================

load_dotenv()

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
KAKAO_API_KEY = os.getenv("KAKAO_REST_API_KEY")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# =====================================
# 2. 웹페이지
# =====================================

HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>음성 내비게이션</title>

<style>

* {
    box-sizing: border-box;
}

body {
    font-family: Arial, sans-serif;
    background: #f1f4f9;
    text-align: center;
    padding: 20px 15px;
    margin: 0;
}

.container {
    max-width: 480px;
    margin: 25px auto;
    padding: 30px 20px;
    background: white;
    border-radius: 20px;
    box-shadow: 0 5px 20px #0002;
}

h1 {
    font-size: 26px;
    color: #222;
}

.description {
    color: #666;
    line-height: 1.6;
}

#speakBtn {
    width: 150px;
    height: 150px;
    border-radius: 50%;
    border: none;
    background: #2864e8;
    color: white;
    font-size: 25px;
    cursor: pointer;
    margin: 20px 0;
    box-shadow: 0 5px 15px #2864e855;
}

#speakBtn:disabled {
    background: #999;
    cursor: not-allowed;
}

#status {
    color: #2864e8;
    font-weight: bold;
    margin: 20px 0;
    min-height: 25px;
}

.speechBox {
    background: #f5f7fb;
    padding: 15px;
    border-radius: 12px;
    margin-top: 20px;
}

#speechResult {
    color: #222;
    font-weight: bold;
    word-break: keep-all;
}

.card {
    padding: 16px;
    margin-top: 15px;
    border: 1px solid #ddd;
    border-radius: 12px;
    text-align: left;
}

.card h3 {
    margin-top: 0;
    color: #222;
}

.address {
    color: #666;
    font-size: 14px;
    line-height: 1.5;
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
    font-weight: bold;
    cursor: pointer;
}

.tmapBtn:active {
    background: #0288d1;
}

.error {
    color: #e53935;
}

.footer {
    font-size: 12px;
    color: #999;
    margin-top: 25px;
}

</style>
</head>

<body>

<div class="container">

    <h1>🚗 음성 내비게이션</h1>

    <p class="description">
        목적지를 음성으로 말씀해주세요.
        <br>
        예: 인천공항으로 가자
    </p>

    <button id="speakBtn">
        🎤<br>말하기
    </button>

    <p id="status">
        말하기 버튼을 눌러주세요.
    </p>

    <div class="speechBox">

        <h3>음성 인식 결과</h3>

        <p id="speechResult">
            입력 대기 중
        </p>

    </div>

    <div id="results"></div>

    <p class="footer">
        OpenAI · Kakao Local · TMAP
    </p>

</div>

<script>

// =====================================
// 1. HTML 요소
// =====================================

const speakBtn = document.getElementById("speakBtn");

const statusText = document.getElementById("status");

const speechResult = document.getElementById("speechResult");

const results = document.getElementById("results");

let isSearching = false;


// =====================================
// 2. 음성인식 지원 확인
// =====================================

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

    recognition.maxAlternatives = 1;


    // =================================
    // 3. 말하기 버튼
    // =================================

    speakBtn.onclick = () => {

        if (isSearching) return;

        speechResult.textContent = "";

        results.innerHTML = "";

        statusText.textContent =
            "🎤 목적지를 말씀해주세요.";

        speakBtn.disabled = true;

        try {

            recognition.start();

        } catch (error) {

            statusText.textContent =
                "음성인식을 다시 시작해주세요.";

            speakBtn.disabled = false;

        }

    };


    // =================================
    // 4. 음성인식 결과
    // =================================

    recognition.onresult = async (event) => {

        const text =
            event.results[0][0].transcript.trim();

        if (!text) {

            statusText.textContent =
                "목적지를 다시 말씀해주세요.";

            return;

        }

        speechResult.textContent = text;

        isSearching = true;

        speakBtn.disabled = true;

        statusText.textContent =
            "🔍 목적지를 검색하고 있습니다.";

        await searchDestination(text);

    };


    // =================================
    // 5. 음성인식 오류
    // =================================

    recognition.onerror = (event) => {

        const messages = {
            "not-allowed": "마이크 권한을 허용해주세요.",
            "no-speech": "음성이 감지되지 않았습니다.",
            "network": "음성인식 네트워크 오류입니다.",
            "audio-capture": "마이크를 확인해주세요."
        };

        statusText.textContent =
            messages[event.error] ||
            "음성인식에 실패했습니다. 다시 시도해주세요.";

    };


    recognition.onend = () => {

        if (!isSearching) {

            speakBtn.disabled = false;

        }

    };

}


// =====================================
// 6. 서버에 목적지 검색 요청
// =====================================

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
            "📍 " + data.destination + " 검색 결과입니다.";

        showPlaces(data.places);

    } catch (error) {

        console.error(error);

        statusText.textContent =
            "서버 연결 오류가 발생했습니다.";

    } finally {

        isSearching = false;

        speakBtn.disabled = false;

    }

}


// =====================================
// 7. 장소 검색 결과 표시
// =====================================

function showPlaces(places) {

    results.innerHTML = "";

    if (!places || places.length === 0) {

        statusText.textContent =
            "검색 결과가 없습니다.";

        return;

    }

    places.forEach((place) => {

        const card = document.createElement("div");

        card.className = "card";


        const title = document.createElement("h3");

        title.textContent = place.name;


        const address = document.createElement("p");

        address.className = "address";

        address.textContent =
            place.address || "주소 정보 없음";


        const button = document.createElement("button");

        button.className = "tmapBtn";

        button.textContent = "🚗 TMAP 길 안내";


        button.onclick = () => {

            if (
                !Number.isFinite(place.longitude) ||
                !Number.isFinite(place.latitude)
            ) {

                alert("목적지 좌표가 없습니다.");

                return;

            }

            const url =
                "tmap://route?goalname=" +
                encodeURIComponent(place.name) +
                "&goalx=" +
                encodeURIComponent(place.longitude) +
                "&goaly=" +
                encodeURIComponent(place.latitude);

            window.location.href = url;

        };


        card.appendChild(title);

        card.appendChild(address);

        card.appendChild(button);

        results.appendChild(card);

    });

}

</script>

</body>
</html>
"""


# =====================================
# 8. 메인 화면
# =====================================

@app.route("/")
def home():

    return render_template_string(HTML)


# =====================================
# 9. 서버 상태 확인
# =====================================

@app.route("/health")
def health():

    return jsonify({
        "success": True,
        "message": "Navigation server is running"
    })


# =====================================
# 10. 목적지 검색
# =====================================

@app.route("/search", methods=["POST"])
def search():

    try:

        # 요청 데이터 확인

        data = request.get_json(silent=True) or {}

        speech_text = data.get("speechText", "")

        if not isinstance(speech_text, str):

            return jsonify({
                "success": False,
                "message": "올바른 음성 입력이 아닙니다."
            }), 400

        speech_text = speech_text.strip()

        if not speech_text:

            return jsonify({
                "success": False,
                "message": "목적지를 말씀해주세요."
            }), 400


        # API 키 확인

        if not OPENAI_API_KEY:

            return jsonify({
                "success": False,
                "message": "OpenAI API 키가 등록되지 않았습니다."
            }), 500

        if not KAKAO_API_KEY:

            return jsonify({
                "success": False,
                "message": "카카오 API 키가 등록되지 않았습니다."
            }), 500


        # =================================
        # 11. OpenAI 목적지 추출
        # =================================

        client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=30.0,
            max_retries=1
        )

        response = client.responses.create(

            model=OPENAI_MODEL,

            instructions="""
            사용자의 한국어 문장에서 내비게이션 목적지만 추출하세요.

            예시:
            서울역으로 가자 -> 서울역
            인천공항 가줘 -> 인천국제공항
            강남역으로 안내해줘 -> 강남역

            목적지를 알 수 없으면 null을 반환하세요.

            주변 설명이나 다른 문장은 반환하지 마세요.
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


        # JSON 결과 처리

        result = json.loads(response.output_text)

        destination = result.get("destination")

        if not destination:

            return jsonify({
                "success": False,
                "message": "목적지를 확인할 수 없습니다. 다시 말씀해주세요."
            }), 400

        destination = destination.strip()

        if not destination:

            return jsonify({
                "success": False,
                "message": "목적지를 다시 말씀해주세요."
            }), 400


        # =================================
        # 12. Kakao Local API 검색
        # =================================

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

            timeout=15

        )

        kakao_response.raise_for_status()

        kakao_data = kakao_response.json()

        documents = kakao_data.get("documents", [])


        if not documents:

            return jsonify({
                "success": False,
                "message": "검색 결과가 없습니다. 다른 이름으로 말씀해주세요."
            }), 404


        # =================================
        # 13. 검색 결과 정리
        # =================================

        places = []

        for p in documents:

            try:

                places.append({

                    "name": p.get("place_name", ""),

                    "address": (
                        p.get("road_address_name")
                        or p.get("address_name")
                        or ""
                    ),

                    "latitude": float(p["y"]),

                    "longitude": float(p["x"])

                })

            except (KeyError, TypeError, ValueError):

                logging.warning(
                    "잘못된 장소 데이터가 있어 제외했습니다."
                )

                continue


        if not places:

            return jsonify({
                "success": False,
                "message": "사용할 수 있는 장소 정보가 없습니다."
            }), 404


        # =================================
        # 14. 결과 반환
        # =================================

        return jsonify({

            "success": True,

            "destination": destination,

            "places": places

        })


    except requests.exceptions.Timeout:

        logging.exception("Kakao API timeout")

        return jsonify({

            "success": False,

            "message": "카카오 장소 검색 시간이 초과되었습니다."

        }), 504


    except requests.exceptions.RequestException:

        logging.exception("Kakao API error")

        return jsonify({

            "success": False,

            "message": "카카오 API 연결에 실패했습니다."

        }), 502


    except Exception:

        logging.exception("Destination search error")

        return jsonify({

            "success": False,

            "message": "검색 오류가 발생했습니다. API 키와 서버 로그를 확인해주세요."

        }), 500


# =====================================
# 15. Render 실행 설정
# =====================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(

        host="0.0.0.0",

        port=port,

        debug=False

    )
