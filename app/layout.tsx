import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '차트 인사이트 | 스마트 투자 뉴스레터',
  description: '노이즈를 걷어낸 단 하나의 스마트한 투자 분석 리포트',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="bg-slate-950 text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}