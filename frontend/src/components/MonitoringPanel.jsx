import React from 'react';
import CarsSeatbeltCard from './CarsSeatbeltCard';
import BikesHelmetCard from './BikesHelmetCard';
import LiveZoomPanel from './LiveZoomPanel';
import RecentResultsList from './RecentResultsList';

export default function MonitoringPanel({
  telemetry,
  recentEvents,
  onSelectEvent
}) {
  const timestamp = telemetry?.timestamp || "01:12";

  return (
    <div className="w-full h-full bg-[#080b0f] border-l border-[#1b2330] flex flex-col p-3 space-y-2.5 overflow-hidden select-none">
      {/* Panel Header */}
      <div className="border-b border-[#1b2330] pb-2 font-mono flex-shrink-0">
        <div className="flex items-center justify-between">
          <h1 className="text-amber-400 font-bold text-sm tracking-wide">
            TRAFFIC VIOLATION MONITOR
          </h1>
          <div className="flex items-center space-x-1.5 bg-[#141b24] px-2 py-0.5 rounded border border-[#232e3d]">
            <span className="w-2 h-2 rounded-full bg-[#ff334b] animate-live-pulse" />
            <span className="text-[11px] font-bold text-[#ff334b] tracking-wider">LIVE</span>
            <span className="text-[11px] text-[#94a3b8] font-semibold">{timestamp}</span>
          </div>
        </div>

        {/* Tech Stack Subtitle */}
        <div className="mt-1 text-[10px] text-[#00e5ff] font-semibold tracking-tight">
          YOLO + BoT-SORT | SEATBELT + HELMET | CHECK ZONE {timestamp}
        </div>
      </div>

      {/* Cars & Seatbelt Section */}
      <CarsSeatbeltCard carStats={telemetry?.car} />

      {/* Bikes & Helmet Section */}
      <BikesHelmetCard 
        bikeStats={telemetry?.bike} 
        timelineTicks={telemetry?.timeline_ticks} 
      />

      {/* Live Zoom Section */}
      <LiveZoomPanel zoomData={telemetry?.zoom} vehicles={telemetry?.vehicles} />

      {/* Recent Results Section (Scrollable) */}
      <RecentResultsList 
        events={recentEvents} 
        onSelectEvent={onSelectEvent} 
      />
    </div>
  );
}
