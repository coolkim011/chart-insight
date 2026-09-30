import os
import sys
import json
import time
import feedparser
import urllib.parse
import urllib.request
import re

def get_live_indices():
    symbols = {
        "코스피": "%5EKS11",
        "코스닥": "%5EKQ11",
        "나스닥": "%5EIXIC",
        "S&P500": "%5EGSPC",
        "필라델피아반도체": "%5ESOX",
        "원/달러": "KRW=X"
    }
    indices_result = []
    for name, sym in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode('utf-8'))
                meta = data['chart']['result'][0]['meta']
                price = meta.get('regularMarketPrice', 0.0)
                prev_close = meta.get('chartPreviousClose', price)
                change = price - prev_close
                change_rate = (change / prev_close) * 100 if prev_close else 0.0
                sign = "+" if change >= 0 else ""
                indices_result.append({
                    "name": name,
                    "price": f"{price:,.2f}",
                    "changeRate": f"{sign}{change_rate:.2f}%",
                    "isUp": change >= 0
                })
        except Exception:
            indices_result.append({
                "name": name,
                "price": "조회중",
                "changeRate": "0.00%",
                "isUp": True
            })
    return indices_result

def fetch_single_stock_rate(code):
    if not code or len(code) != 6:
        return {"changeRate": "0.00%", "isUp": True}
    
    # 코스피/코스닥 심볼 접미사 처리 (우선 코스닥/코스피 자동 탐색)
    symbols_to_try = [f"{code}.KQ", f"{code}.KS"]
    for sym in symbols_to_try:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=3) as res:
                data = json.loads(res.read().decode('utf-8'))
                meta = data['chart']['result'][0]['meta']
                price = meta.get('regularMarketPrice', 0.0)
                prev_close = meta.get('chartPreviousClose', price)
                if price and prev_close:
                    change = price - prev_close
                    change_rate = (change / prev_close) * 100
                    sign = "+" if change >= 0 else ""
                    return {
                        "changeRate": f"{sign}{change_rate:.2f}%",
                        "isUp": change >= 0
                    }
        except Exception:
            continue
    return {"changeRate": "0.00%", "isUp": True}

RSS_SOURCES = [
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "Investing.com", "url": "https://kr.investing.com/rss/news.rss"},
    {"name": "한국경제", "url": "https://www.hankyung.com/feed/finance"}
]

SMART_MAPPINGS = [
    {
        "keywords": ["robot", "humanoid", "automation", "로봇", "휴머노이드", "자동화"],
        "theme": "휴머노이드 로봇 및 제조 자동화 산업",
        "categoryBadge": "로봇/자동화",
        "summary": [
            "글로벌 주요국 및 기업들의 휴머노이드 로봇 표준 규격 및 기술 가이드라인 발표",
            "산업 현장 내 로봇 도입 확대 및 AI 피지컬 컴퓨팅 적용 가속화",
            "정밀 모터, 감속기, 관절 구동기 등 핵심 부품 중심의 공급망 형성"
        ],
        "stocks": [
            {"rank": 1, "name": "레인보우로보틱스", "code": "277810", "role": "완제품 플랫폼", "reason": "이족보행 플랫폼 및 삼성전자 제조라인 협동로봇 공급"},
            {"rank": 2, "name": "에스피지", "code": "058610", "role": "정밀 감속기 국산화", "reason": "로봇 핵심 구동 부품인 SH/SR 정밀감속기 양산 공급"},
            {"rank": 3, "name": "에스비비테크", "code": "389260", "role": "하모닉 감속기", "reason": "소형 로봇 관절용 초정밀 하모닉 드라이브 제조"},
            {"rank": 4, "name": "알에스오토메이션", "code": "140670", "role": "모션제어·드라이브", "reason": "로봇 관절 구동 스마트 모션컨트롤러 기술 보유"}
        ]
    },
    {
        "keywords": ["polymarket", "crypto", "bitcoin", "blockchain", "goldman", "가상자산", "비트코인", "코인", "거래소"],
        "theme": "디지털 자산 및 핀테크 제도권 동향",
        "categoryBadge": "디지털자산/핀테크",
        "summary": [
            "글로벌 블록체인 예측 및 거래 플랫폼의 전통 금융권(월가) 전문 인력 영입",
            "디지털 자산의 제도권 금융 시스템 편입 및 관련 금융 상품 다양화",
            "국내외 가상자산 거래 인프라 및 결제 네트워크의 시장 영향 점검"
        ],
        "stocks": [
            {"rank": 1, "name": "우리기술투자", "code": "041190", "role": "거래소 1대 지분", "reason": "국내 1위 거래소 업비트 운영사 두나무 핵심 지분 보유"},
            {"rank": 2, "name": "한화투자증권", "code": "003530", "role": "핀테크 지분 보유", "reason": "두나무 주요 주주 및 토큰증권 협의체 참여"},
            {"rank": 3, "name": "갤럭시아머니트리", "code": "094480", "role": "STO/결제인프라", "reason": "항공금융·신재생에너지 기반 토큰증권 발행 인프라 선점"},
            {"rank": 4, "name": "핑거", "code": "163730", "role": "금융 핀테크 솔루션", "reason": "제1금융권 블록체인 및 디지털 자산 지갑 솔루션 공급"}
        ]
    },
    {
        "keywords": ["chip", "semiconductor", "hbm", "intel", "nvidia", "amd", "micron", "반도체", "하이닉스", "삼성전자", "optical", "광통신"],
        "theme": "차세대 반도체 광통신 및 첨단 패키징",
        "categoryBadge": "반도체/소부장",
        "summary": [
            "차세대 초고속 데이터 전송(광통신/실리콘 포토닉스) 및 인터페이스 연구 개발",
            "인공지능(AI) 가속기 병목 현상 해소를 위한 광학 패키징 기술 대두",
            "국내 첨단 후공정 장비 및 광통신 부품 기업 중심의 공급망 재편"
        ],
        "stocks": [
            {"rank": 1, "name": "한미반도체", "code": "042700", "role": "TC본더 독점 장비", "reason": "글로벌 HBM 열압착 패키징 장비 시장 독점 지배력"},
            {"rank": 2, "name": "이수페타시스", "code": "007660", "role": "초고다층 PCB 기판", "reason": "글로벌 빅테크 AI 가속기용 초고다층 회로기판(MLB) 공급"},
            {"rank": 3, "name": "오이솔루션", "code": "138080", "role": "광트랜시버 부품", "reason": "데이터센터용 초고속 광트랜시버 및 레이저 다이오드 개발"},
            {"rank": 4, "name": "네오셈", "code": "253590", "role": "차세대 CXL 검사장비", "reason": "차세대 메모리 규격 CXL 및 고속 검사장비 선점"},
            {"rank": 5, "name": "디아이티", "code": "252110", "role": "레이저 어닐링 장비", "reason": "첨단 반도체 수율 향상용 레이저 공정 장비 납품"}
        ]
    },
    {
        "keywords": ["bond", "debt", "treasury", "trump", "rate", "fed", "채권", "국채", "금리", "지방채", "s&p", "tariff"],
        "theme": "글로벌 거시경제 및 금융 매크로",
        "categoryBadge": "금융/거시경제",
        "summary": [
            "글로벌 주요국 통화정책 기조 변화 및 증시 구성 종목 간 디커플링 심화",
            "국채 금리 및 재정 정책 변화에 따른 자산 시장 포트폴리오 재편",
            "대외 교역 환경 변화 및 수급 변동성에 따른 주요 업종별 영향 점검"
        ],
        "stocks": [
            {"rank": 1, "name": "KB금융", "code": "105560", "role": "종합금융그룹", "reason": "안정적 대출 및 채권 포트폴리오를 보유한 대표 금융지주"},
            {"rank": 2, "name": "삼성전자", "code": "005930", "role": "글로벌 IT 대장", "reason": "지수 변동성 구간 내 기관·외인 수급 중심 역할"},
            {"rank": 3, "name": "키움증권", "code": "039490", "role": "브로커리지", "reason": "자산시장 거래대금 증가에 따른 수수료 수혜"}
        ]
    }
]

def analyze_with_ai(headline, summary, client):
    if not client:
        return None
    try:
        prompt = f"""
당신은 한국 주식시장의 소부장(소재·부품·장비) 및 서플라이 체인을 꿰뚫고 있는 수석 밸류체인 분석가입니다.
어떠한 투자 유도나 매수 권유 없이, 오직 객관적 사실(Fact) 기반의 뉴스 요약과 밸류체인을 작성하세요.

[기사 제목]
{headline}

[기사 본문]
{summary}

규칙:
1. newsHeadlineKo: 한국 금융 전문지 스타일의 매끄러운 한글 번역 제목 (영어 원문 그대로 두지 말 것)
2. newsSummaryKo: 기사 본문에 명시된 객관적 사실만 3문장으로 간결하게 정리
3. categoryBadge: 로봇/자동화, 디지털자산/핀테크, 반도체/소부장, 금융/거시경제 중 적합한 것 1개 선택
4. stocks: 해당 산업의 직접 부품/장비/소재를 납품하는 코스닥/코스피 소부장 벤더 위주로 3~4개 엄선

반드시 순수 JSON 객체만 반환:
{{
  "theme": "핵심 주제명",
  "categoryBadge": "산업 섹터명",
  "newsHeadlineKo": "한글 번역 제목",
  "newsSummaryKo": [
    "기사 팩트 요약 1",
    "기사 팩트 요약 2",
    "기사 팩트 요약 3"
  ],
  "stocks": [
    {{"rank": 1, "name": "상장사명", "code": "6자리코드", "role": "구체적 역할", "reason": "객관적 연관 사실"}}
  ]
}}
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        raw = response.text.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  [AI 오류 발생: {e}]")
        return None

def fallback_analysis(headline, summary):
    text_corp = (headline + " " + summary).lower()
    for cat in SMART_MAPPINGS:
        if any(k in text_corp for k in cat["keywords"]):
            return {
                "theme": cat["theme"],
                "categoryBadge": cat["categoryBadge"],
                "newsHeadlineKo": headline,
                "newsSummaryKo": cat.get("summary", []),
                "stocks": cat["stocks"]
            }
    return {
        "theme": "글로벌 마켓 및 산업 공급망 동향",
        "categoryBadge": "금융/거시경제",
        "newsHeadlineKo": f"글로벌 주요 경제 속보: {headline[:30]}...",
        "newsSummaryKo": [
            "글로벌 주요 경제 지표 및 기업 공시 내용이 새롭게 발표됨.",
            "국제 금융 시장 및 관련 산업 밸류체인 내 단기 변동성 점검 필요.",
            "국내외 동종 업계 공급망 및 주요 기업들의 대응 현황 모니터링."
        ],
        "stocks": [
            {"rank": 1, "name": "SK하이닉스", "code": "000660", "role": "메모리 대장주", "reason": "글로벌 IT 및 반도체 공급망 핵심 기업"},
            {"rank": 2, "name": "한미반도체", "code": "042700", "role": "후공정 장비", "reason": "첨단 패키징 장비 독점 지배력 보유"}
        ]
    }

def run():
    print("==================================================")
    print("1. 실시간 글로벌 지수 및 환율 수집...")
    live_indices = get_live_indices()

    existing_briefings = []
    seen_links = set()
    seen_titles = set()
    
    briefing_file = "public/briefing.json"
    if os.path.exists(briefing_file):
        try:
            with open(briefing_file, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                existing_briefings = old_data.get("briefings", [])
                for b in existing_briefings:
                    if b.get("newsLink"):
                        seen_links.add(b["newsLink"])
                    if b.get("newsHeadlineOriginal"):
                        seen_titles.add(b["newsHeadlineOriginal"])
            print(f"  ✓ 기존 저장된 과거 기사: 총 {len(existing_briefings)}건 보존 확인")
        except Exception as e:
            print(f"  기존 데이터 로드 예외: {e}")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    client = None
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            print("  ✓ Gemini AI 엔진 활성화 성공")
        except Exception as e:
            print(f"  Gemini 클라이언트 연결 실패: {e}")

    print("\n2. 멀티 뉴스 피드 수집...")
    new_articles = []

    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "#")
                if not title or link in seen_links or title in seen_titles:
                    continue
                seen_links.add(link)
                seen_titles.add(title)
                new_articles.append({
                    "title": title,
                    "summary": entry.get("summary", ""),
                    "link": link,
                    "source": src["name"],
                    "published": entry.get("published", "실시간")[:16]
                })
        except Exception as e:
            print(f"  [{src['name']}] 수집 에러: {e}")

    print(f"  새로 감지된 최신 기사: {len(new_articles)}건")

    new_briefings = []
    target_articles = new_articles[:5] if new_articles else []

    if target_articles:
        print(f"\n3. 신규 기사 분석 및 실시간 종목 등락률 수집...")
        for art in target_articles:
            headline = art["title"]
            summary = art["summary"]
            print(f"  분석 중: {headline[:35]}...")

            data = analyze_with_ai(headline, summary, client)
            if not data or not data.get("newsHeadlineKo"):
                data = fallback_analysis(headline, summary)

            # 종목별 실시간 등락률 주입
            stocks_data = data.get("stocks", [])
            for st in stocks_data:
                code = st.get("code", "")
                rate_info = fetch_single_stock_rate(code)
                st["changeRate"] = rate_info["changeRate"]
                st["isUp"] = rate_info["isUp"]

            new_briefings.append({
                "id": int(time.time() * 1000) + len(new_briefings),
                "theme": data.get("theme", "산업 주요 이슈"),
                "categoryBadge": data.get("categoryBadge", "금융/거시경제"),
                "newsHeadlineOriginal": headline,
                "newsHeadlineKo": data.get("newsHeadlineKo", headline),
                "newsSummaryKo": data.get("newsSummaryKo", []),
                "newsSource": f"{art['source']} · {art['published']}",
                "newsLink": art["link"],
                "stocks": stocks_data
            })
            time.sleep(0.5)

    # 기존 기사 종목들 중 등락률이 비어있는 경우 채워넣기 (상위 5건만 업데이트)
    for b in existing_briefings[:5]:
        for st in b.get("stocks", []):
            if "changeRate" not in st:
                code = st.get("code", "")
                rate_info = fetch_single_stock_rate(code)
                st["changeRate"] = rate_info["changeRate"]
                st["isUp"] = rate_info["isUp"]

    combined_briefings = new_briefings + existing_briefings
    combined_briefings = combined_briefings[:100]

    for idx, item in enumerate(combined_briefings):
        item["id"] = idx + 1

    data_payload = {
        "indices": live_indices,
        "briefings": combined_briefings
    }

    os.makedirs("public", exist_ok=True)
    with open(briefing_file, "w", encoding="utf-8") as f:
        json.dump(data_payload, f, ensure_ascii=False, indent=2)

    print(f"\n최종 완료: 등락률이 반영된 총 {len(combined_briefings)}건 저장 완료!")

if __name__ == "__main__":
    run()