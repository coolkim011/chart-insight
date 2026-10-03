import os
import sys
import json
import time
import feedparser
import urllib.error
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
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-flash-latest,gemini-flash-lite-latest").split(",") if m.strip()
]

TIER_LIMITS = {1: 2, 2: 3, 3: 3}   # 1차(대장주) / 2차 / 3차 최대 종목 수

# 실행과 실행 사이에 기억해 둘 AI 상태(모델별 한도 소진 시각). briefing.json의 aiState에 저장된다.
AI_STATE = {"blocked": {}}

# 무료 AI 호출은 하루 횟수가 적어서, 한국 종목과 연결될 만한 뉴스만 분석 대상으로 삼는다
RELEVANT_KEYWORDS = [
    # 산업·기업
    "chip", "semiconductor", "hbm", "memory", "nvidia", "micron", "tsmc", "samsung", "hynix", "intel", "amd", "broadcom",
    "ai ", " ai", "data center", "datacenter", "robot", "humanoid", "automation", "battery", "lithium", "ev ", "electric vehicle",
    "tesla", "apple", "shipbuilding", "defense", "nuclear", "uranium", "solar", "hydrogen", "bio", "pharma", "obesity", "glp-1",
    "steel", "oil", "crude", "lng", "refin", "copper", "gold", "rare earth", "display", "oled", "5g", "satellite", "space",
    "game", "k-pop", "cosmetic", "korea", "korean", "seoul", "kospi", "kosdaq", "won ",
    # 거시·가상자산
    "fed ", "federal reserve", "rate cut", "interest rate", "inflation", "tariff", "trade war", "treasury", "bond", "dollar",
    "china", "yuan", "japan", "yen", "bitcoin", "crypto", "blockchain", "stablecoin", "etf",
    # 한국어
    "반도체", "메모리", "로봇", "자동화", "배터리", "전기차", "2차전지", "조선", "방산", "원전", "원자력", "태양광", "수소",
    "바이오", "제약", "비만", "철강", "석유", "정유", "구리", "금값", "디스플레이", "위성", "우주", "게임", "화장품",
    "코스피", "코스닥", "삼성", "하이닉스", "현대", "엔비디아", "금리", "환율", "관세", "국채", "비트코인", "가상자산", "코인", "블록체인",
]


def is_relevant(headline, summary=""):
    text = f" {headline} {summary} ".lower()
    return any(k in text for k in RELEVANT_KEYWORDS)


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


def _norm_name(name):
    return re.sub(r"\(주\)|㈜|\s", "", name or "").lower()


def verify_stock(code, name):
    """종목코드가 실제 상장 종목인지, AI가 쓴 종목명과 일치하는지 네이버 증권으로 확인한다.

    반환: ("ok", 공식 종목명) / ("invalid", 사유) / ("unknown", None)
    unknown은 조회 자체가 실패한 경우(네트워크 등)로, 이때는 AI 결과를 그대로 둔다.
    """
    url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            info = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (404, 409):
            return "invalid", "존재하지 않는 종목코드"
        return "unknown", None
    except Exception:
        return "unknown", None

    official = info.get("stockName")
    if not official:
        return "invalid", "존재하지 않는 종목코드"
    a, b = _norm_name(name), _norm_name(official)
    if a and (a == b or a in b or b in a):
        return "ok", official
    return "invalid", f"종목명 불일치(AI: {name} / 실제: {official})"


def verify_stocks(stocks):
    """코드·종목명이 맞지 않는 종목은 버리고, 맞는 종목은 공식 종목명으로 바로잡는다."""
    verified = []
    for st in stocks:
        status, detail = verify_stock(st["code"], st["name"])
        if status == "invalid":
            print(f"  [종목 제외: {st['code']} {detail}]")
            continue
        if status == "ok":
            st["name"] = detail
            st["verified"] = True
        verified.append(st)
    for idx, st in enumerate(verified):
        st["rank"] = idx + 1
    return verified


def requeue_legacy_fallbacks(briefings):
    """예전 기본 분석으로 저장된 기사(번역 없음·엉뚱한 종목)를 AI 분석 대기로 되돌린다."""
    count = 0
    for b in briefings:
        if b.get("status"):
            continue
        ko, orig = b.get("newsHeadlineKo", ""), b.get("newsHeadlineOriginal", "")
        if ko.startswith("글로벌 주요 경제 속보") or (orig and ko == orig):
            relevant = is_relevant(orig or ko)
            b.update({
                "theme": "AI 분석 대기 중" if relevant else "분석 제외",
                "newsHeadlineKo": "",
                "newsSummaryKo": [],
                "stocks": [],
                "status": "pending" if relevant else "skipped",
            })
            if relevant:
                b.update({"attempts": 0, "rawSummary": ""})
            count += 1
    if count:
        print(f"  예전 기본 분석 기사 {count}건을 재분석 대기로 전환")


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
   - 기사와 직접 연결이 약하더라도 같은 업종·테마로 엮이는 국내 상장사가 있으면 tier 2~3에 포함하고, reason에 그 연결 고리를 한 문장으로 분명히 쓰세요.
   - 한국 상장사와 정말 연결할 수 없는 기사(예: 해외 소형주 개별 실적)만 stocks를 빈 배열로 두세요.
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


class AIUnavailable(Exception):
    """오늘은 더 이상 AI를 쓸 수 없는 상태(무료 한도 소진·전 모델 과부하). 기사 탓이 아니므로 시도 횟수에 넣지 않는다."""


def _retry_seconds(msg):
    """오류 메시지에서 '몇 초 뒤에 다시 시도하라'는 값을 읽는다. 없으면 일일 한도는 6시간, 그 외는 60초."""
    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s", msg)
    if m:
        return float(m.group(1))
    m = re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", msg)
    if m and any(m.groups()):
        h, mi, s = (float(g) if g else 0.0 for g in m.groups())
        return h * 3600 + mi * 60 + s
    return 6 * 3600 if "PerDay" in msg else 60


def _short(msg, n=90):
    return re.sub(r"\s+", " ", str(msg))[:n]


def _gemini_generate(api, prompt):
    """모델별 한도를 기억해 두고, 한도가 찬 모델은 건너뛰며 다음 모델로 넘어간다."""
    models = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    blocked = AI_STATE.setdefault("blocked", {})
    now = time.time()
    available = [m for m in models if blocked.get(m, 0) <= now]

    for model_name in available:
        for attempt in range(3):
            try:
                return api.models.generate_content(model=model_name, contents=prompt).text.strip()
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    wait = _retry_seconds(msg)
                    if wait <= 120 and attempt < 2:      # 분당 한도: 잠깐 기다렸다가 같은 모델로 재시도
                        print(f"  [{model_name} 분당 한도, {int(wait) + 1}초 후 재시도]")
                        time.sleep(wait + 1)
                        continue
                    blocked[model_name] = time.time() + max(wait, 600)
                    print(f"  [{model_name} 호출 한도 초과 → 약 {max(wait, 600) / 3600:.1f}시간 동안 사용 안 함]")
                    break
                if "404" in msg or "NOT_FOUND" in msg:
                    blocked[model_name] = time.time() + 86400
                    print(f"  [{model_name} 사용할 수 없는 모델 → 오늘은 건너뜀: {_short(msg)}]")
                    break
                if any(c in msg for c in ("503", "UNAVAILABLE", "overloaded")) and attempt < 2:
                    wait = 5 * (attempt + 1)
                    print(f"  [일시 과부하({model_name}) → {wait}초 후 재시도 ({attempt + 1}/2)]")
                    time.sleep(wait)
                    continue
                if any(c in msg for c in ("503", "UNAVAILABLE", "overloaded")):
                    print(f"  [{model_name} 계속 과부하 → 다음 모델 시도]")
                    break
                raise
    raise AIUnavailable("사용 가능한 Gemini 모델이 없음(한도 소진 또는 과부하)")


def call_llm(prompt, client):
    """선택된 AI로 호출하고 응답 텍스트를 돌려준다. 쓸 수 없는 상태면 AIUnavailable."""
    provider, api = client
    if provider == "gemini":
        return _gemini_generate(api, prompt)

    try:
        response = api.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}]
        )
    except Exception as e:
        if any(c in str(e) for c in ("429", "529", "overloaded", "credit balance")):
            raise AIUnavailable(_short(e))
        raise
    if response.stop_reason == "refusal":
        raise ValueError("AI가 응답을 거절함")
    return "".join(b.text for b in response.content if b.type == "text").strip()


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
        raw_count = len(data.get("stocks") or [])
        data["stocks"] = normalize_stocks(data.get("stocks"))
        print(f"  종목: AI 제안 {raw_count}개 → 형식 검증 후 {len(data['stocks'])}개")
        return data
    except AIUnavailable:
        raise
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
                data = json.load(f)
            AI_STATE["blocked"] = dict(data.get("aiState", {}).get("blocked", {}))
            return data
        except Exception as e:
            print(f"  기존 데이터 로드 예외: {e}")
    return {"indices": [], "briefings": []}


def save_briefing_file(indices, briefings):
    briefings = briefings[:MAX_BRIEFINGS]
    for idx, item in enumerate(briefings):
        item["id"] = idx + 1
    now = time.time()
    ai_state = {"blocked": {m: t for m, t in AI_STATE.get("blocked", {}).items() if t > now}}
    os.makedirs("public", exist_ok=True)
    with open(BRIEFING_FILE, "w", encoding="utf-8") as f:
        json.dump({"indices": indices, "briefings": briefings, "aiState": ai_state}, f, ensure_ascii=False, indent=2)


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
            from google.genai import types
            print(f"  ✓ Gemini AI 엔진 활성화 성공 ({GEMINI_MODEL})")
            # 응답이 오지 않고 멈추는 경우를 막기 위해 호출당 60초 제한
            return ("gemini", genai.Client(api_key=gemini_key, http_options=types.HttpOptions(timeout=60000)))
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
                raw_summary = clean_text(entry.get("summary", ""))
                relevant = is_relevant(title, raw_summary)
                item = {
                    "id": 0,
                    "theme": "AI 분석 대기 중" if relevant else "분석 제외",
                    "categoryBadge": "글로벌 마켓",
                    "newsHeadlineOriginal": title,
                    "newsHeadlineKo": "",
                    "newsSummaryKo": [],
                    "newsSource": f"{src['name']} · {entry.get('published', '실시간')[:16]}",
                    "newsLink": link,
                    "stocks": [],
                    "status": "pending" if relevant else "skipped",
                }
                if relevant:
                    item["attempts"] = 0
                    item["rawSummary"] = raw_summary
                new_items.append(item)
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
    if client:
        requeue_legacy_fallbacks(briefings)

    # 이미 대기열에 있던 기사도 관련성 필터를 거쳐, 한도를 쓸 필요가 없는 기사는 분석 대상에서 뺀다
    for b in briefings:
        if b.get("status") == "pending" and not is_relevant(b.get("newsHeadlineOriginal", ""), b.get("rawSummary", "")):
            b.update({"status": "skipped", "theme": "분석 제외"})
            b.pop("attempts", None)
            b.pop("rawSummary", None)

    pending = [b for b in briefings if b.get("status") == "pending"]
    print(f"  분석 대기: {len(pending)}건 (이번 실행에서 최대 {MAX_AI_PER_RUN}건 처리)")

    if client:
        # Gemini 무료 한도(분당 호출 수)를 넘지 않도록 호출 사이에 간격을 둔다
        delay = float(os.environ.get("AI_CALL_DELAY", "4" if client[0] == "gemini" else "0"))
        for item in pending[:MAX_AI_PER_RUN]:
            headline = item.get("newsHeadlineOriginal", "")
            print(f"  분석 중: {headline[:35]}...")
            try:
                result = analyze_with_ai(headline, item.get("rawSummary", ""), client)
            except AIUnavailable as e:
                # 한도 소진·과부하: 기사 잘못이 아니므로 시도 횟수에 넣지 않고 오늘 분석은 여기서 멈춘다
                print(f"  [AI 사용 불가: {e}] 남은 기사는 다음 실행에서 분석합니다.")
                break

            if result:
                item["theme"] = result.get("theme") or "산업 주요 이슈"
                item["categoryBadge"] = result.get("categoryBadge") or "글로벌 마켓"
                item["newsHeadlineKo"] = result["newsHeadlineKo"]
                item["newsSummaryKo"] = result.get("newsSummaryKo", [])
                item["stocks"] = verify_stocks(result["stocks"])
                print(f"  종목 확인 후 최종 {len(item['stocks'])}개")
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
