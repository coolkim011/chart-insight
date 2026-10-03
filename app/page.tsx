"use client";

import React, { useState, useEffect } from "react";

interface Stock {
  rank?: number;
  tier?: number;
  verified?: boolean;
  name: string;
  code: string;
  role: string;
  reason: string;
  changeRate?: string;
  isUp?: boolean;
}

interface BriefingItem {
  id: number;
  theme: string;
  categoryBadge: string;
  newsHeadlineKo?: string;
  newsHeadlineOriginal?: string;
  newsHeadline?: string;
  newsSummaryKo: string[];
  newsSource: string;
  newsLink: string;
  stocks: Stock[];
  status?: "pending" | "done" | "failed";
}

const TIER_LABELS: Record<number, { title: string; desc: string; color: string }> = {
  1: { title: "1차 · 대장주", desc: "뉴스와 가장 직접 연결된 종목", color: "text-rose-400 bg-rose-500/15" },
  2: { title: "2차 · 공급망 연결", desc: "대장주에 직접 공급·연결된 종목", color: "text-amber-400 bg-amber-500/15" },
  3: { title: "3차 · 간접 연관", desc: "한 단계 건너 연결된 후방 종목", color: "text-sky-400 bg-sky-500/15" },
};

const REFRESH_MS = 5 * 60 * 1000;

interface MarketIndex {
  name: string;
  price: string;
  changeRate: string;
  isUp: boolean;
}

const CATEGORIES = ["전체", "글로벌 마켓", "금융/거시경제", "디지털자산/핀테크", "로봇/자동화", "반도체/소부장"];

export default function Home() {
  const [indices, setIndices] = useState<MarketIndex[]>([]);
  const [briefings, setBriefings] = useState<BriefingItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("전체");
  const [searchQuery, setSearchQuery] = useState("");
  // 기사 id는 새 뉴스가 올라올 때마다 바뀌므로 링크를 기준으로 펼침 상태를 기억한다
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [shareToast, setShareToast] = useState(false);
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [showBookmarksOnly, setShowBookmarksOnly] = useState(false);
  const [visibleCount, setVisibleCount] = useState(8);

  useEffect(() => {
    const loadData = () => {
      fetch("/briefing.json", { cache: "no-store" })
        .then((res) => res.json())
        .then((data) => {
          if (data.indices) setIndices(data.indices);
          if (data.briefings) setBriefings(data.briefings);
        })
        .catch((err) => console.error("데이터 로드 실패:", err));
    };

    loadData();
    // 새 뉴스가 올라오면 새로고침 없이 반영되도록 주기적으로 다시 불러온다
    const timer = setInterval(loadData, REFRESH_MS);

    const saved = localStorage.getItem("chart_insight_bookmarks");
    if (saved) {
      try {
        setBookmarks(JSON.parse(saved));
      } catch (e) {
        console.error(e);
      }
    }

    return () => clearInterval(timer);
  }, []);

  const toggleBookmark = (e: React.MouseEvent, code: string) => {
    e.stopPropagation();
    let updated: string[];
    if (bookmarks.includes(code)) {
      updated = bookmarks.filter((c) => c !== code);
    } else {
      updated = [...bookmarks, code];
    }
    setBookmarks(updated);
    localStorage.setItem("chart_insight_bookmarks", JSON.stringify(updated));
  };

  const toggleExpand = (key: string) => {
    setExpandedItems((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleCopy = (e: React.MouseEvent, code: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 1500);
  };

  const handleShare = (e: React.MouseEvent, item: BriefingItem) => {
    e.stopPropagation();
    const title = item.newsHeadlineKo || item.newsHeadline || item.newsHeadlineOriginal || "";
    const summary = item.newsSummaryKo.join("\n- ");
    const text = `[차트 인사이트 브리핑]\n\n📌 ${title}\n\n- ${summary}\n\n🔗 원문: ${item.newsLink}`;
    navigator.clipboard.writeText(text);
    setShareToast(true);
    setTimeout(() => setShareToast(false), 2000);
  };

  const openNaverFinance = (e: React.MouseEvent, code: string) => {
    e.stopPropagation();
    window.open(`https://finance.naver.com/item/main.naver?code=${code}`, "_blank");
  };

  const filteredBriefings = briefings.filter((item) => {
    const matchCat = selectedCategory === "전체" || item.categoryBadge === selectedCategory;
    const headline = (item.newsHeadlineKo || item.newsHeadline || item.newsHeadlineOriginal || "").toLowerCase();
    const q = searchQuery.toLowerCase().trim();
    const matchQuery =
      !q ||
      headline.includes(q) ||
      (item.theme || "").toLowerCase().includes(q) ||
      item.stocks.some((s) => s.name.toLowerCase().includes(q) || s.code.includes(q));

    const matchBookmark = !showBookmarksOnly || item.stocks.some((s) => bookmarks.includes(s.code));
    return matchCat && matchQuery && matchBookmark;
  });

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 flex flex-col items-center">
      {/* 1. 상단 글로벌 지수 티커 전광판 */}
      <div className="w-full bg-[#0b0e14] border-b border-slate-800/80 overflow-x-auto scrollbar-none py-2 px-4 flex items-center space-x-6 text-xs font-mono select-none">
        {indices.map((idx) => (
          <div key={idx.name} className="flex items-center space-x-1.5 flex-shrink-0">
            <span className="text-slate-400 font-semibold">{idx.name}</span>
            <span className="text-white font-bold">{idx.price}</span>
            <span className={`font-bold ${idx.isUp ? "text-rose-400" : "text-blue-400"}`}>
              {idx.changeRate}
            </span>
          </div>
        ))}
      </div>

      {/* 2. 메인 컨테이너 */}
      <main className="w-full max-w-2xl px-4 py-6 flex flex-col space-y-4">
        {/* 헤더 */}
        <header className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <h1 className="text-xl font-black tracking-tight text-white font-mono">CHART INSIGHT</h1>
          </div>
          <button
            onClick={() => setShowBookmarksOnly(!showBookmarksOnly)}
            className={`px-3 py-1 rounded-full text-xs font-bold transition flex items-center space-x-1 ${
              showBookmarksOnly ? "bg-amber-500 text-black" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            <span>★ 관심종목 ({bookmarks.length})</span>
          </button>
        </header>

        {/* 검색창 */}
        <div className="relative">
          <input
            type="text"
            placeholder="종목명(한글), 티커, 테마 검색 (예: 한미반도체, 에스피지)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#111622] border border-slate-800 rounded-xl px-4 py-2.5 pl-10 text-sm focus:outline-none focus:border-blue-500 transition placeholder:text-slate-500"
          />
          <span className="absolute left-3.5 top-2.5 text-slate-500 text-sm">🔍</span>
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-2.5 text-xs text-slate-400 hover:text-white"
            >
              ✕
            </button>
          )}
        </div>

        {/* 카테고리 필터 탭 */}
        <div className="flex items-center space-x-2 overflow-x-auto scrollbar-none pb-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition ${
                selectedCategory === cat
                  ? "bg-blue-600 text-white"
                  : "bg-[#111622] text-slate-400 hover:text-white border border-slate-800/80"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* 브리핑 카드 피드 */}
        <section className="space-y-4 pt-1">
          {filteredBriefings.slice(0, visibleCount).map((item) => {
            const headlineKo = item.newsHeadlineKo || item.newsHeadline;
            const headlineEn = item.newsHeadlineOriginal;
            const itemKey = item.newsLink || String(item.id);
            const isExpanded = !!expandedItems[itemKey];
            const isPending = item.status === "pending";
            const isFailed = item.status === "failed";
            // 1차·2차·3차 순으로 묶는다. tier 정보가 없는 예전 기사는 하나의 목록으로 보여준다
            const stockGroups = [1, 2, 3, 0]
              .map((tier) => ({
                tier,
                stocks: item.stocks.filter((s) => (TIER_LABELS[s.tier ?? 0] ? s.tier : 0) === tier),
              }))
              .filter((g) => g.stocks.length > 0);

            return (
              <article
                key={itemKey}
                className="bg-[#0e121a] border border-slate-800/90 rounded-2xl p-4 shadow-lg hover:border-slate-700 transition flex flex-col space-y-3"
              >
                {/* 뱃지 및 테마 */}
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded font-black text-[10px]">
                      NEW
                    </span>
                    <span className="font-extrabold text-white text-xs">{item.theme}</span>
                  </div>
                  <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded text-[10px] font-bold">
                    {item.categoryBadge}
                  </span>
                </div>

                {/* 바이링구얼 헤드라인 */}
                <div className="space-y-1">
                  <h2 className="text-base font-extrabold text-white leading-snug tracking-tight">
                    {headlineKo || headlineEn}
                  </h2>
                  {headlineEn && (
                    <p className="text-xs text-slate-400/80 italic font-sans leading-tight">
                      {headlineEn}
                    </p>
                  )}
                </div>

                {/* 언론사 및 액션 버튼 */}
                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/60">
                  <span>{item.newsSource}</span>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={(e) => handleShare(e, item)}
                      className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded-md font-bold transition flex items-center space-x-1"
                    >
                      <span>🖨 요약공유</span>
                    </button>
                    <a
                      href={item.newsLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-blue-400 font-bold transition"
                    >
                      원문 ↗
                    </a>
                  </div>
                </div>

                {/* AI 분석 대기 / 실패 안내 */}
                {isPending && (
                  <div className="bg-[#121722] rounded-xl p-3 text-xs text-slate-400 border border-dashed border-slate-700 flex items-center space-x-2">
                    <span className="animate-pulse">⏳</span>
                    <span>AI가 번역·요약과 관련 종목을 분석하는 중입니다. 잠시 후 자동으로 채워집니다.</span>
                  </div>
                )}
                {isFailed && (
                  <div className="bg-[#121722] rounded-xl p-3 text-xs text-slate-500 border border-slate-800/60">
                    이 기사는 AI 분석을 완료하지 못했습니다. 원문을 참고해 주세요.
                  </div>
                )}

                {/* 팩트 요약 3줄 */}
                {!isPending && !isFailed && item.newsSummaryKo.length > 0 && (
                  <div className="bg-[#121722] rounded-xl p-3 text-xs space-y-1.5 border border-slate-800/60">
                    <div className="text-[11px] font-extrabold text-slate-300 flex items-center space-x-1 mb-1">
                      <span>📋 외신 핵심 사실 요약</span>
                    </div>
                    {item.newsSummaryKo.map((sum, sIdx) => (
                      <div key={sIdx} className="flex items-start space-x-2 text-slate-300 leading-relaxed">
                        <span className="text-blue-400 mt-0.5">•</span>
                        <span>{sum}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* 밸류체인 연관 기업 아코디언 */}
                {!isPending && !isFailed && item.stocks.length > 0 && (
                <div className="border border-slate-800/80 rounded-xl overflow-hidden bg-[#0c1017]">
                  <button
                    onClick={() => toggleExpand(itemKey)}
                    className="w-full flex items-center justify-between p-3 text-xs font-bold text-slate-200 hover:bg-slate-800/40 transition"
                  >
                    <div className="flex items-center space-x-2">
                      <span className="text-amber-400">⚡</span>
                      <span>산업 밸류체인 연관 기업 ({item.stocks.length}개)</span>
                    </div>
                    <span className="text-slate-400 text-[10px]">
                      {isExpanded ? "▲ 접기" : "▼ 상세보기"}
                    </span>
                  </button>

                  {isExpanded && (
                    <div className="p-3 pt-0 space-y-3 border-t border-slate-800/60">
                      {stockGroups.map((group) => (
                      <div key={group.tier} className="space-y-2 pt-3">
                      {group.tier > 0 && (
                        <div className="flex items-center space-x-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-black ${TIER_LABELS[group.tier].color}`}>
                            {TIER_LABELS[group.tier].title}
                          </span>
                          <span className="text-[10px] text-slate-500">{TIER_LABELS[group.tier].desc}</span>
                        </div>
                      )}
                      {group.stocks.map((stock, idx) => {
                        const displayRank = stock.rank || idx + 1;
                        const isBookmarked = bookmarks.includes(stock.code);

                        return (
                          <div
                            key={stock.code}
                            className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-[#0d131f] p-2.5 transition hover:border-slate-700"
                          >
                            <div className="flex items-start space-x-2 min-w-0 pr-2">
                              <button
                                onClick={(e) => toggleBookmark(e, stock.code)}
                                className="text-base leading-none pt-0.5 text-amber-400 hover:scale-110 transition"
                              >
                                {isBookmarked ? "★" : "☆"}
                              </button>

                              <span className="flex-shrink-0 flex items-center justify-center w-5 h-5 rounded text-[11px] font-black font-mono mt-0.5 bg-slate-800 text-slate-300">
                                {displayRank}
                              </span>

                              <div className="min-w-0">
                                <div className="flex items-center space-x-1.5 flex-wrap">
                                  <span className="text-sm font-extrabold text-white">{stock.name}</span>
                                  <span className="font-mono text-xs text-slate-400">{stock.code}</span>
                                  {stock.verified && (
                                    <span title="종목코드와 종목명이 실제 상장 정보와 일치합니다" className="text-[10px] text-emerald-400">
                                      ✓확인
                                    </span>
                                  )}

                                  {/* 실시간 등락률 배지 */}
                                  {stock.changeRate && (
                                    <span
                                      className={`font-mono text-[10px] font-black px-1.5 py-0.5 rounded border ${
                                        stock.isUp
                                          ? "text-rose-400 bg-rose-950/40 border-rose-800/50"
                                          : "text-blue-400 bg-blue-950/40 border-blue-800/50"
                                      }`}
                                    >
                                      {stock.changeRate}
                                    </span>
                                  )}

                                  <button
                                    onClick={(e) => openNaverFinance(e, stock.code)}
                                    className="text-[10px] text-emerald-400 hover:underline font-medium"
                                  >
                                    [차트 ↗]
                                  </button>
                                </div>
                                <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
                                  <span className="rounded bg-slate-800 px-1.5 py-0.2 text-[10px] font-semibold text-slate-300">
                                    {stock.role}
                                  </span>
                                  <span className="text-[11px] text-slate-300/90">{stock.reason}</span>
                                </div>
                              </div>
                            </div>

                            <button
                              onClick={(e) => handleCopy(e, stock.code)}
                              className="flex-shrink-0 rounded-lg px-2.5 py-1.5 text-[11px] font-bold bg-blue-600 hover:bg-blue-500 text-white transition active:scale-95"
                            >
                              {copiedCode === stock.code ? "✓ 완료" : "코드복사"}
                            </button>
                          </div>
                        );
                      })}
                      </div>
                      ))}
                    </div>
                  )}
                </div>
                )}
              </article>
            );
          })}
        </section>

        {/* 이전 브리핑 더보기 버튼 */}
        {visibleCount < filteredBriefings.length && (
          <div className="pt-2 pb-6 flex justify-center">
            <button
              onClick={() => setVisibleCount((prev) => prev + 8)}
              className="w-full bg-[#121722] hover:bg-[#1a2233] border border-slate-800 text-slate-300 font-bold py-3 rounded-xl text-xs transition"
            >
              + 이전 브리핑 더보기 ({filteredBriefings.length - visibleCount}개 남음)
            </button>
          </div>
        )}
        {/* 면책 안내 */}
        <p className="pb-8 text-center text-[10px] leading-relaxed text-slate-500">
          본 서비스의 관련 종목은 AI가 뉴스 내용을 바탕으로 정리한 참고 정보이며, 투자 권유나 매수·매도 추천이 아닙니다.
          종목 연관성과 종목코드는 부정확할 수 있으니 투자 판단과 그 결과의 책임은 이용자 본인에게 있습니다.
        </p>
      </main>

      {/* 공유 토스트 알림 */}
      {shareToast && (
        <div className="fixed bottom-6 bg-emerald-600 text-white px-4 py-2 rounded-xl text-xs font-bold shadow-2xl animate-bounce">
          ✓ 핵심 사실 요약이 클립보드에 복사되었습니다!
        </div>
      )}
    </div>
  );
}