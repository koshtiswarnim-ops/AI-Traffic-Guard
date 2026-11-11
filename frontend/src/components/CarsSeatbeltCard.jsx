import React from 'react';

export default function CarsSeatbeltCard({ carStats }) {
  const stats = carStats || { total: 0, checking: 0, compliant: 0, violation: 0, compliance_pct: 0 };
  const compliance = stats.total > 0 ? (stats.compliance_pct ?? 0) : 0;

  return (
    <div className="bg-[#0c1017] border border-[#1b2330] rounded-sm p-3 font-mono">
      {/* Card Header */}
      <div className="flex items-center justify-between border-b border-[#1b2330] pb-1.5 mb-2.5">
        <span className="text-amber-400 font-bold text-xs tracking-wide">
          CARS | SEATBELT
        </span>
        <span className="text-emerald-400 text-xs font-semibold">
          compliance {stats.total > 0 ? `${compliance}%` : '--%'}
        </span>
      </div>

      {/* 4 Counter Columns Grid */}
      <div className="grid grid-cols-4 gap-2 text-center">
        {/* TOTAL */}
        <div className="flex flex-col">
          <span className="text-[10px] text-[#64748b] uppercase tracking-wider mb-0.5">TOTAL</span>
          <span className="text-xl font-bold text-[#00e5ff] tracking-tight tabular-nums">
            {stats.total}
          </span>
        </div>

        {/* CHECKING */}
        <div className="flex flex-col border-l border-[#1b2330]">
          <span className="text-[10px] text-[#64748b] uppercase tracking-wider mb-0.5">CHECKING</span>
          <span className="text-xl font-bold text-amber-400 tracking-tight tabular-nums">
            {stats.checking}
          </span>
        </div>

        {/* SEATBELT */}
        <div className="flex flex-col border-l border-[#1b2330]">
          <span className="text-[10px] text-[#64748b] uppercase tracking-wider mb-0.5">SEATBELT</span>
          <span className="text-xl font-bold text-[#00e676] tracking-tight tabular-nums">
            {stats.compliant}
          </span>
        </div>

        {/* NO SEATBELT */}
        <div className="flex flex-col border-l border-[#1b2330]">
          <span className="text-[10px] text-[#64748b] uppercase tracking-wider mb-0.5">NO SEATBELT</span>
          <span className="text-xl font-bold text-[#ff334b] tracking-tight tabular-nums">
            {stats.violation}
          </span>
        </div>
      </div>

      {/* Compliance Indicator Bar */}
      <div className="mt-2.5 w-full h-1 bg-[#16202c] rounded-full overflow-hidden flex">
        {stats.total > 0 && (
          <>
            <div 
              className="h-full bg-[#00e676] transition-all duration-300" 
              style={{ width: `${compliance}%` }}
            />
            <div 
              className="h-full bg-[#ff334b] transition-all duration-300" 
              style={{ width: `${100 - compliance}%` }}
            />
          </>
        )}
      </div>
    </div>
  );
}
