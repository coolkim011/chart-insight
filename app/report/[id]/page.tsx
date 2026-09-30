import React from 'react';
import Link from 'next/link';

// 더미 리포트 데이터
const reportDetails: Record<string, {
  category: string;
  title: string;
  date: string;
  readTime: string;
  author: string;
  isPremium: boolean;
  content: string[];
  keyPoints: string[];
}> = {
  '1': {
    category: '테크 & 반도체',
    title: '차세대 HBM 공급망 재편과 엔비디아의 차기 로드맵 심층 분석',
    date: '2026.09.28',
    readTime: '7분',
    author: 'AI 인프라 리서치팀',
    isPremium: true,
    keyPoints: [
      '엔비디아 루빈 아키텍처 출시 계획에 따른 6세대 HBM4 수요 예측치 상향',
      '패키징 수율 안정화 구간 진입 및 국내 주요 공급망 밸류체인 점검',
      '하반기 글로벌 빅테크 CAPEX 투자 지속성 검증'
    ],
    content: [
      '글로벌 생성형 AI 인프라 투자 사이클이 훈련(Training) 중심에서 추론(Inference) 단계로 확장되면서, 대역폭과 메모리 용량을 동시에 만족해야 하는 HBM 수요가 견고하게 유지되고 있습니다.',
      '특히 주요 파운드리 및 패키징 거점의 공정 안정화가 가속됨에 따라 하반기 공급 물량에 대한 가시성이 높아졌습니다. 이는 단기 가격 협상력뿐만 아니라 중장기 마진 구조에도 긍정적인 신호로 작용할 전망입니다.',
      '투자 관점에서는 단일 칩셋 공급사보다 패키징 소재, 검사장비, 열 관리 솔루션 등 기술 장벽이 높은 서브 밸류체인 중심의 선별적 접근이 유효할 것으로 판단됩니다.'
    ]
  },
  '2': {
    category: '매크로 브리핑',
    title: '미국 연준 금리 인하 사이클 진입: 자산군별 기대 수익률 포트폴리오',
    date: '2026.09.27',
    readTime: '5분',
    author: '매크로 전략팀',
    isPremium: false,
    keyPoints: [
      '기준금리 인하 국면 진입 시 과거 주요 자산군 백테스팅 결과 비교',
      '장단기 국채 금리차 역전 해소 과정에서의 유동성 쏠림 현상 점검',
      '고배당 가치주 및 신흥국 채권 포트폴리오 비중 확대 권고'
    ],
    content: [
      '미 연방준비제도의 통화정책 기조 전환이 가시화되면서 전통적인 60/40 자산배분 모델의 재평가가 이뤄지고 있습니다.',
      '역사적 데이터를 분석해보면 금리 인하 초기 국면에서는 단기 변동성이 확대되는 경향이 있으나, 유동성 완화가 정착되는 중기 시점부터는 배당 자산과 듀레이션이 긴 채권군이 강력한 하방 지지력을 보였습니다.',
      '따라서 공격적인 지수 추종 레버리지보다는 안정적인 현금흐름을 확보할 수 있는 인컴형 자산 배분을 권장합니다.'
    ]
  },
  '3': {
    category: '바이오 & 헬스케어',
    title: '비만 치료제 파이프라인 경쟁 심화: 새로운 타깃 기술의 부상',
    date: '2026.09.25',
    readTime: '6분',
    author: '바이오 애널리스트',
    isPremium: true,
    keyPoints: [
      'GLP-1 복합 수용체 작용제의 후기 임상 결과 및 안전성 데이터',
      '경구용 제형 전환에 따른 글로벌 대량 위탁생산(CDMO) 수혜 전망',
      '단순 체중 감량에서 심혈관·신장 질환 확장 승인에 따른 시장 규모 확대'
    ],
    content: [
      '비만 치료제 시장은 기존 주사제 중심에서 투약 편의성을 대폭 개선한 경구용 제형과 복합 작용제 중심으로 2차 경쟁 국면에 돌입했습니다.',
      '적응증 확대와 더불어 대규모 생산 역량을 보유한 주요 CDMO 기업들의 수주 잔고가 빠르게 늘어나고 있으며, 약물 전달 기술을 보유한 플랫폼 기업들에 대한 밸류에이션 프리미엄이 부각되고 있습니다.',
      '임상 모멘텀에 따른 단기 변동성을 고려하되, 실제 상업화 생산 설비를 갖춘 실적 기반 공급망 기업 위주의 비중 전략이 요구됩니다.'
    ]
  }
};

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const report = reportDetails[params.id] || reportDetails['1'];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <main className="mx-auto max-w-4xl px-4 py-12">
        {/* 상단 네비게이션 */}
        <div className="mb-8">
          <Link
            href="/"
            className="inline-flex items-center text-sm font-medium text-slate-400 hover:text-slate-200"
          >
            &larr; 메인 리포트 목록으로 돌아가기
          </Link>
        </div>

        {/* 리포트 헤더 */}
        <header className="border-b border-slate-800 pb-8">
          <div className="flex items-center gap-3">
            <span className="rounded bg-slate-800 px-2.5 py-1 text-xs font-medium text-blue-400">
              {report.category}
            </span>
            {report.isPremium && (
              <span className="rounded bg-amber-500/10 px-2.5 py-0.5 text-xs font-semibold text-amber-400 ring-1 ring-amber-500/20">
                VIP REPORT
              </span>
            )}
          </div>
          <h1 className="mt-4 text-2xl font-bold tracking-tight text-white sm:text-4xl">
            {report.title}
          </h1>
          <div className="mt-4 flex items-center gap-4 text-xs text-slate-400 sm:text-sm">
            <span>작성: {report.author}</span>
            <span>·</span>
            <span>{report.date}</span>
            <span>·</span>
            <span>{report.readTime} 읽기</span>
          </div>
        </header>

        {/* 핵심 요약 포인트 */}
        <section className="my-8 rounded-xl border border-blue-500/20 bg-blue-950/20 p-6">
          <h2 className="text-base font-semibold text-blue-300">핵심 브리핑 요약</h2>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-slate-300">
            {report.keyPoints.map((point, idx) => (
              <li key={idx}>{point}</li>
            ))}
          </ul>
        </section>

        {/* 리포트 본문 내용 */}
        <article className="space-y-6 text-base leading-relaxed text-slate-300">
          {report.content.map((paragraph, idx) => (
            <p key={idx}>{paragraph}</p>
          ))}
        </article>

        {/* 하단 구독 CTA 영역 */}
        {report.isPremium && (
          <section className="mt-16 rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-center">
            <h3 className="text-lg font-bold text-white">전체 분석 리포트 및 포트폴리오 비중 확인</h3>
            <p className="mt-2 text-sm text-slate-400">
              구독자 전용 섹션입니다. 프리미엄 뉴스레터를 신청하고 심층 차트 데이터 및 목표 주가 모델을 확인하세요.
            </p>
            <button className="mt-4 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md transition hover:bg-blue-500">
              VIP 리포트 전체 보기
            </button>
          </section>
        )}
      </main>
    </div>
  );
}