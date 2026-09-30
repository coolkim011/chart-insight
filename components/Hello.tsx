interface HelloProps {
  name?: string;
  className?: string;
}

export default function Hello({ name = "게스트", className = "" }: HelloProps) {
  const currentHour = new Date().getHours();
  
  const getGreeting = () => {
    if (currentHour < 12) return "좋은 아침입니다";
    if (currentHour < 18) return "즐거운 오후입니다";
    return "편안한 저녁 되세요";
  };

  return (
    <div
      className={`inline-flex flex-col gap-1 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      <span className="text-sm font-medium text-slate-500 dark:text-slate-400">
        {getGreeting()}
      </span>
      <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
        안녕하세요, <span className="text-blue-600 dark:text-blue-400">{name}</span>님! 👋
      </h2>
    </div>
  );
}