import React from 'react';

export default function RecentResultsList({ events, onSelectEvent }) {
  const displayEvents = events || [];

  return (
    <div className="bg-[#0c1017] border border-[#1b2330] rounded-sm p-3 font-mono flex-1 flex flex-col min-h-0">
      {/* Section Header */}
      <div className="flex items-center justify-between border-b border-[#1b2330] pb-1.5 mb-2 flex-shrink-0">
        <span className="text-amber-400 font-bold text-xs tracking-wide">
          RECENT RESULTS
        </span>
        <span className="text-[10px] text-[#64748b]">
          {displayEvents.length} RECORDED
        </span>
      </div>

      {/* Vertically Scrollable Event Cards List */}
      <div className="overflow-y-auto space-y-1.5 flex-1 pr-1 custom-scrollbar min-h-[140px]">
        {displayEvents.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center py-6 text-[11px] text-[#475569] tracking-wide">
            MONITORING ZONE — NO EVENTS RECORDED YET
          </div>
        ) : (
          displayEvents.map((ev, idx) => {
            const isViolation = ev.is_violation || (ev.status && ev.status.toUpperCase().includes("NO"));
            const indicatorColor = isViolation ? 'border-l-[#ff334b]' : 'border-l-[#00e676]';
            const statusTextColor = isViolation ? 'text-[#ff334b]' : 'text-[#00e676]';

            return (
              <div
                key={ev.id || idx}
                onClick={() => onSelectEvent && onSelectEvent(ev)}
                className={`flex items-center justify-between bg-[#080b0f] hover:bg-[#121822] p-2 border-l-4 ${indicatorColor} border border-[#1a2332] rounded-sm transition-all cursor-pointer group`}
              >
                {/* Left Thumbnail + Vehicle Info */}
                <div className="flex items-center space-x-2.5">
                  <div className="w-10 h-10 bg-[#16202c] border border-[#232f42] rounded-sm overflow-hidden flex-shrink-0 flex items-center justify-center">
                    {ev.thumbnail_url ? (
                      <img
                        src={ev.thumbnail_url}
                        alt={`Vehicle ${ev.vehicle_id}`}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                    ) : (
                      <span className="text-[9px] text-[#475569]">N/A</span>
                    )}
                  </div>

                  {/* ID & Status */}
                  <div className="flex flex-col justify-center leading-tight">
                    <div className="flex items-center space-x-1.5">
                      <span className="text-xs font-bold text-[#e2e8f0] group-hover:text-[#00e5ff] transition-colors">
                        {ev.vehicle_type} ID{ev.vehicle_id}
                      </span>
                      {ev.is_verified && (
                        <span className="text-[9px] px-1 bg-emerald-950 text-emerald-400 border border-emerald-600 rounded">
                          VERIFIED
                        </span>
                      )}
                    </div>
                    <span className={`text-[11px] font-bold ${statusTextColor}`}>
                      {ev.status}
                    </span>
                  </div>
                </div>

                {/* Right Timestamp & Camera Info */}
                <div className="flex flex-col items-end text-[10px] text-[#64748b] leading-tight space-y-0.5">
                  <span className="text-[#94a3b8] font-mono">{ev.timestamp || "00:00"}</span>
                  <span className="text-[9px] text-[#475569]">{ev.camera_id || "CAM 01"}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
