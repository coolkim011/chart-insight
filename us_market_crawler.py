import os
import sys
import json
import time
import feedparser
import urllib.parse
import urllib.request
import re

BRIEFING_FILE = "public/briefing.json"
MAX_BRIEFINGS = 100
MAX_NEW_PER_RUN = 20       # 한 번에 목록에 올리는 신규 기사 상한
MAX_AI_PER_RUN = int(os.environ.get("MAX_AI_PER_RUN", "8"))   # 한 번에 AI 분석하는 기사 상한
MAX_ATTEMPTS = 6           # 이 횟수만큼 분석에 실패하면 포기(failed)

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

TIER_LIMITS = {1: 2, 2: 3, 3: 3}   # 1차(대장주) / 2차 / 3차 최대 종목 수


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
    """종목 등락률 조회. 조회에 실패하면 빈 dict를 돌려준다(가짜 0.00%를 만들지 않음)."""
    if not code or len(code) != 6:
        return {}

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
    return {}


RSS_SOURCES = [
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "Investing.com", "url": "https://kr.investing.com/rss/news.rss"},
    {"name": "한국경제", "url": "https://www.hankyung.com/feed/finance"}
]


def build_prompt(headline, summary):
    return f"""
당신은 한국 주식시장의 소부장(소재·부품·장비) 및 서플라이 체인을 꿰뚫고 있는 수석 밸류체인 분석가입니다.
어떠한 투자 유도나 매수 권유 없이, 오직 객관적 사실(Fact) 기반의 뉴스 요약과 밸류체인을 작성하세요.

[기사 제목]
{headline}

[기사 본문]
{summary}

규칙:
1. newsHeadlineKo: 한국 금융 전문지 스타일의 매끄러운 한글 번역 제목 (영어 원문 그대로 두지 말 것)
2. newsSummaryKo: 기사 본문에 명시된 객관적 사실만 3문장으로 간결하게 정리
3. categoryBadge: 글로벌 마켓, 금융/거시경제, 디지털자산/핀테크, 로봇/자동화, 반도체/소부장 중 적합한 것 1개 선택
4. stocks: 코스피/코스닥에 실제 상장된 종목만 tier(1~3)를 붙여 작성
   - tier 1 (1차·대장주): 이 뉴스로 가장 직접적이고 즉각적인 영향을 받는 대표 종목 1~2개
   - tier 2 (2차): 대장주에 부품·소재·장비·서비스를 공급하는 등 직접 연결된 종목 최대 3개
   - tier 3 (3차): 한 단계 더 건너 간접적으로 연결된 후방·파생 관련 종목 최대 3개
   - 연관성이 분명하지 않은 tier는 비워 두세요. 한국 상장사와 관련이 없는 기사면 stocks는 빈 배열입니다.
   - 종목코드는 정확한 6자리를 확신할 때만 쓰고, 확신이 없으면 그 종목은 제외하세요.
   - reason에는 매수 권유가 아닌 객관적 연관 사실만 쓰세요.

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
    {{"tier": 1, "name": "상장사명", "code": "6자리코드", "role": "구체적 역할", "reason": "객관적 연관 사실"}}
  ]
}}
"""


def call_llm(prompt, client):
    """선택된 AI로 호출하고 응답 텍스트를 돌려준다. 일시 오류(503/429/529)는 재시도."""
    provider, api = client
    for attempt in range(4):
        try:
            if provider == "gemini":
                return api.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                ).text.strip()
            response = api.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": prompt}]
            )
            if response.stop_reason == "refusal":
                raise ValueError("AI가 응답을 거절함")
            return "".join(b.text for b in response.content if b.type == "text").strip()
        except Exception as e:
            transient = any(c in str(e) for c in ("503", "429", "529", "overloaded"))
            if attempt < 3 and transient:
                wait = 5 * (attempt + 1)
                print(f"  [일시 오류, {wait}초 후 재시도 ({attempt + 1}/3)]")
                time.sleep(wait)
                continue
            raise


def normalize_stocks(raw_stocks):
    """AI가 돌려준 종목 목록을 tier 순으로 정리하고 형식이 틀린 항목은 버린다."""
    by_tier = {1: [], 2: [], 3: []}
    seen_codes = set()
    for st in raw_stocks or []:
        try:
            tier = int(st.get("tier", 0))
        except (TypeError, ValueError):
            continue
        code = str(st.get("code", "")).strip()
        name = str(st.get("name", "")).strip()
        if tier not in by_tier or not name or not re.fullmatch(r"\d{6}", code) or code in seen_codes:
            continue
        seen_codes.add(code)
        by_tier[tier].append({
            "tier": tier,
            "name": name,
            "code": code,
            "role": str(st.get("role", "")).strip(),
            "reason": str(st.get("reason", "")).strip(),
        })

    stocks = []
    for tier in (1, 2, 3):
        stocks.extend(by_tier[tier][:TIER_LIMITS[tier]])
    for idx, st in enumerate(stocks):
        st["rank"] = idx + 1
    return stocks


def analyze_with_ai(headline, summary, client):
    """성공하면 분석 결과 dict, 실패하면 None."""
    if not client:
        return None
    try:
        raw = call_llm(build_prompt(headline, summary), client)
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("JSON 객체를 찾을 수 없음")
        data = json.loads(raw[start:end + 1])
        if not data.get("newsHeadlineKo"):
            raise ValueError("번역 제목이 비어 있음")
        data["stocks"] = normalize_stocks(data.get("stocks"))
        return data
    except Exception as e:
        print(f"  [AI 오류 발생: {e}]")
        return None


def clean_text(html, limit=1500):
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def load_briefing_file():
    if os.path.exists(BRIEFING_FILE):
        try:
            with open(BRIEFING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"  기존 데이터 로드 예외: {e}")
    return {"indices": [], "briefings": []}


def save_briefing_file(indices, briefings):
    briefings = briefings[:MAX_BRIEFINGS]
    for idx, item in enumerate(briefings):
        item["id"] = idx + 1
    os.makedirs("public", exist_ok=True)
    with open(BRIEFING_FILE, "w", encoding="utf-8") as f:
        json.dump({"indices": indices, "briefings": briefings}, f, ensure_ascii=False, indent=2)


def make_client():
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if anthropic_key:
        try:
            import anthropic
            print(f"  ✓ Claude AI 엔진 활성화 성공 ({CLAUDE_MODEL})")
            return ("claude", anthropic.Anthropic(api_key=anthropic_key))
        except Exception as e:
            print(f"  Claude 클라이언트 연결 실패: {e}")
    if gemini_key:
        try:
            from google import genai
            print(f"  ✓ Gemini AI 엔진 활성화 성공 ({GEMINI_MODEL})")
            return ("gemini", genai.Client(api_key=gemini_key))
        except Exception as e:
            print(f"  Gemini 클라이언트 연결 실패: {e}")
    print("  AI 키 없음: 분석 대기 상태로 유지")
    return None


def collect():
    """1단계: 새 뉴스를 감지해 AI 분석 없이 먼저 목록에 올린다."""
    print("==================================================")
    print("1. 실시간 글로벌 지수 및 환율 수집...")
    live_indices = get_live_indices()

    old_data = load_briefing_file()
    existing = old_data.get("briefings", [])
    seen_links = {b["newsLink"] for b in existing if b.get("newsLink")}
    seen_titles = {b["newsHeadlineOriginal"] for b in existing if b.get("newsHeadlineOriginal")}
    print(f"  ✓ 기존 저장된 과거 기사: 총 {len(existing)}건 보존 확인")

    print("\n2. 멀티 뉴스 피드 수집...")
    new_items = []
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
                new_items.append({
                    "id": 0,
                    "theme": "AI 분석 대기 중",
                    "categoryBadge": "글로벌 마켓",
                    "newsHeadlineOriginal": title,
                    "newsHeadlineKo": "",
                    "newsSummaryKo": [],
                    "newsSource": f"{src['name']} · {entry.get('published', '실시간')[:16]}",
                    "newsLink": link,
                    "stocks": [],
                    "status": "pending",
                    "attempts": 0,
                    "rawSummary": clean_text(entry.get("summary", "")),
                })
        except Exception as e:
            print(f"  [{src['name']}] 수집 에러: {e}")

    new_items = new_items[:MAX_NEW_PER_RUN]
    print(f"  새로 감지된 최신 기사: {len(new_items)}건 (분석 전에 먼저 목록에 게시)")
    save_briefing_file(live_indices, new_items + existing)


def analyze():
    """2단계: 분석 대기 중인 기사를 AI로 분석해 번역·요약·1~3차 종목을 채운다."""
    print("\n3. 분석 대기 기사 AI 분석...")
    data = load_briefing_file()
    briefings = data.get("briefings", [])
    client = make_client()

    pending = [b for b in briefings if b.get("status") == "pending"]
    print(f"  분석 대기: {len(pending)}건 (이번 실행에서 최대 {MAX_AI_PER_RUN}건 처리)")

    if client:
        # Gemini 무료 한도(분당 호출 수)를 넘지 않도록 호출 사이에 간격을 둔다
        delay = float(os.environ.get("AI_CALL_DELAY", "4" if client[0] == "gemini" else "0"))
        for item in pending[:MAX_AI_PER_RUN]:
            headline = item.get("newsHeadlineOriginal", "")
            print(f"  분석 중: {headline[:35]}...")
            result = analyze_with_ai(headline, item.get("rawSummary", ""), client)

            if result:
                item["theme"] = result.get("theme") or "산업 주요 이슈"
                item["categoryBadge"] = result.get("categoryBadge") or "글로벌 마켓"
                item["newsHeadlineKo"] = result["newsHeadlineKo"]
                item["newsSummaryKo"] = result.get("newsSummaryKo", [])
                item["stocks"] = result["stocks"]
                item["status"] = "done"
                item.pop("rawSummary", None)
                item.pop("attempts", None)
                for st in item["stocks"]:
                    st.update(fetch_single_stock_rate(st["code"]))
            else:
                item["attempts"] = item.get("attempts", 0) + 1
                if item["attempts"] >= MAX_ATTEMPTS:
                    item["status"] = "failed"
                    item["theme"] = "분석 실패"
                    item.pop("rawSummary", None)
            time.sleep(delay)

    # 기존 기사 종목들 중 등락률이 비어있는 경우 채워넣기 (상위 5건만 업데이트)
    for b in briefings[:5]:
        for st in b.get("stocks", []):
            if "changeRate" not in st:
                st.update(fetch_single_stock_rate(st.get("code", "")))

    save_briefing_file(data.get("indices", []), briefings)
    done = sum(1 for b in briefings if b.get("status") == "pending")
    print(f"\n최종 완료: 총 {min(len(briefings), MAX_BRIEFINGS)}건 저장 (분석 대기 {done}건 남음)")


def run(mode="all"):
    if mode in ("all", "collect"):
        collect()
    if mode in ("all", "analyze"):
        analyze()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "all")
