import React, { useState, useEffect, useRef } from 'react';
import CctvPlayer from './components/CctvPlayer';
import MonitoringPanel from './components/MonitoringPanel';
import BottomStatusBar from './components/BottomStatusBar';
import CameraModal from './components/CameraModal';
import VerificationModal from './components/VerificationModal';

export default function App() {
  const [telemetry, setTelemetry] = useState({
    timestamp: "00:00",
    fps: 0.0,
    frame_idx: 0,
    total_frames: 0,
    camera_id: "CAM 01",
    camera_name: "AR2 Highway Surveillance Cam 01",
    location: "Ayesha Buni Sh Faisal AR2",
    status: "CONNECTING",
    operating_mode: "DEMO / SIMULATION MODE (YOLOv8 + CV)",
    is_pre_annotated: true,
    car: { total: 0, checking: 0, compliant: 0, violation: 0, compliance_pct: 0 },
    bike: { total: 0, checking: 0, compliant: 0, violation: 0, compliance_pct: 0 },
    timeline_ticks: [],
    zoom: { has_target: false, crop_b64: null, id: null, type: null, status: null, is_violation: false, conf: 0.0, timestamp: "00:00" },
    toasts: [],
    vehicles: [],
    zone_polygon: [
      [40, 480],
      [1310, 480],
      [1260, 335],
      [80, 335]
    ]
  });

  const [recentEvents, setRecentEvents] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [streamKey, setStreamKey] = useState(Date.now());
  const [isCameraModalOpen, setIsCameraModalOpen] = useState(false);
  const [selectedVerificationEvent, setSelectedVerificationEvent] = useState(null);

  const [isPaused, setIsPaused] = useState(false);
  const [cameraConfig, setCameraConfig] = useState({
    id: "CAM 01",
    name: "AR2 Highway Surveillance Cam 01",
    location: "Ayesha Buni Sh Faisal AR2"
  });

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const fetchEvents = async () => {
    try {
      const res = await fetch("/api/events");
      if (res.ok) {
        const data = await res.json();
        setRecentEvents(data || []);
      }
    } catch (e) {
      // Handled by WS reconnect
    }
  };

  const fetchInitialStatus = async () => {
    try {
      const [statusRes, telRes] = await Promise.all([
        fetch("/api/status"),
        fetch("/api/telemetry")
      ]);
      if (statusRes.ok) {
        const st = await statusRes.json();
        setIsPaused(Boolean(st.is_paused));
        setCameraConfig({
          id: st.active_camera || "CAM 01",
          name: st.camera_name || "AR2 Highway Surveillance Cam 01",
          location: st.location || "Ayesha Buni Sh Faisal AR2"
        });
      }
      if (telRes.ok) {
        const tel = await telRes.json();
        if (tel && tel.car) {
          setTelemetry(prev => ({ ...prev, ...tel }));
        }
      }
    } catch (e) {
      // Backend initializing
    }
  };

  useEffect(() => {
    fetchInitialStatus();
    fetchEvents();
  }, []);

  // Connect WebSocket to FastAPI Backend (/api/ws/live)
  useEffect(() => {
    let isMounted = true;

    const connectWs = () => {
      if (!isMounted) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/api/ws/live`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted) return;
        setWsConnected(true);
        console.log("[WebSocket] Connected to AI TrafficGuard live engine");
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "TELEMETRY") {
            setTelemetry(prev => ({
              ...prev,
              ...payload,
              vehicles: payload.vehicles ?? prev.vehicles,
              car: payload.car ?? prev.car,
              bike: payload.bike ?? prev.bike,
              zoom: payload.zoom ?? prev.zoom,
              toasts: payload.toasts ?? [],
              timeline_ticks: payload.timeline_ticks ?? prev.timeline_ticks
            }));
          } else if (payload.type === "NEW_EVENT") {
            const ev = payload.event;
            setRecentEvents(prev => [
              ev,
              ...prev.filter(item => !(item.camera_id === ev.camera_id && item.vehicle_id === ev.vehicle_id))
            ].slice(0, 100));
          } else if (payload.type === "EVENT_VERIFIED") {
            setRecentEvents(prev => prev.map(ev => ev.id === payload.event.id ? payload.event : ev));
          }
        } catch (err) {
          console.error("WS Parse error", err);
        }
      };

      ws.onclose = () => {
        if (!isMounted) return;
        setWsConnected(false);
        reconnectTimeoutRef.current = setTimeout(connectWs, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWs();

    return () => {
      isMounted = false;
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, []);

  const handleTogglePause = async () => {
    try {
      const res = await fetch("/api/control/pause", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setIsPaused(Boolean(data.is_paused));
      } else {
        setIsPaused(!isPaused);
      }
    } catch (e) {
      setIsPaused(!isPaused);
    }
  };

  const handleReconnect = async () => {
    try {
      await fetch("/api/control/reconnect", { method: "POST" });
    } catch (e) {}
    setStreamKey(Date.now());
  };

  const handleSelectCamera = async (cam) => {
    setCameraConfig({
      id: cam.id,
      name: cam.name,
      location: cam.loc || "Highway"
    });

    try {
      const formData = new FormData();
      formData.append("id", cam.id);
      formData.append("name", cam.name);
      formData.append("source_type", cam.source_type || "video");
      formData.append("source_url", cam.path);
      formData.append("location", cam.loc || "Highway");
      await fetch("/api/cameras", { method: "POST", body: formData });
      setStreamKey(Date.now());
    } catch (e) {}
  };

  const handleAddRtspCamera = async (camData) => {
    const formData = new FormData();
    formData.append("id", camData.id);
    formData.append("name", camData.name);
    formData.append("source_type", "rtsp");
    formData.append("source_url", camData.source_url);
    formData.append("location", camData.location);

    const res = await fetch("/api/cameras", { method: "POST", body: formData });
    if (!res.ok) throw new Error("Backend could not open RTSP connection");

    const data = await res.json();
    setCameraConfig({
      id: camData.id,
      name: camData.name,
      location: camData.location
    });
    setStreamKey(Date.now());

    if (data.stream_status && data.stream_status.includes("OFFLINE")) {
      throw new Error(data.stream_status);
    }
  };

  const handleUploadVideo = async (file) => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/api/upload", { method: "POST", body: formData });
    if (!res.ok) throw new Error("Upload failed on backend");

    setCameraConfig({
      id: "CAM 01",
      name: `Custom Video: ${file.name}`,
      location: "Uploaded File Testing"
    });
    setStreamKey(Date.now());
  };

  const handleUpdateZone = async (newPts) => {
    try {
      await fetch("/api/zone", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newPts)
      });
    } catch (e) {}
  };

  const handleConfirmVerification = async ({ eventId, status, verifiedBy, notes }) => {
    const formData = new FormData();
    formData.append("verified_status", status);
    formData.append("verified_by", verifiedBy);
    if (notes) formData.append("notes", notes);

    const res = await fetch(`/api/events/${eventId}/verify`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) throw new Error("Verification API failed");
    fetchEvents();
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#080b0f] text-[#e2e8f0] overflow-hidden">
      {/* Main Surveillance Display: 72% CCTV Stream + 28% Right Monitoring Panel */}
      <div className="flex-1 flex overflow-hidden w-full h-[calc(100vh-28px)]">
        {/* Left ~72% Width CCTV Video Area */}
        <div className="w-[72%] h-full relative overflow-hidden bg-black border-r border-[#16202c]">
          <CctvPlayer
            telemetry={telemetry}
            cameraConfig={cameraConfig}
            isPaused={isPaused}
            streamKey={streamKey}
            wsConnected={wsConnected}
            onTogglePause={handleTogglePause}
            onReconnect={handleReconnect}
            onOpenSourceModal={() => setIsCameraModalOpen(true)}
            onUpdateZone={handleUpdateZone}
            operatingMode={telemetry?.operating_mode}
          />
        </div>

        {/* Right ~28% Width Monitoring Panel */}
        <div className="w-[28%] h-full relative overflow-hidden bg-[#080b0f]">
          <MonitoringPanel
            telemetry={telemetry}
            recentEvents={recentEvents}
            onSelectEvent={(ev) => setSelectedVerificationEvent(ev)}
          />
        </div>
      </div>

      {/* Bottom Status Bar */}
      <BottomStatusBar
        viewMode="DETECTION"
        fps={telemetry?.fps ?? 0.0}
        processedFrames={telemetry?.frame_idx ?? 0}
        totalFrames={telemetry?.total_frames ?? 0}
        activeCamera={`${cameraConfig.id} (${cameraConfig.name})`}
      />

      {/* Camera & Video Source Configuration Modal */}
      <CameraModal
        isOpen={isCameraModalOpen}
        onClose={() => setIsCameraModalOpen(false)}
        onSelectCamera={handleSelectCamera}
        onAddRtspCamera={handleAddRtspCamera}
        onUploadVideo={handleUploadVideo}
        currentCameraId={cameraConfig.id}
      />

      {/* Manual Violation Verification Modal */}
      <VerificationModal
        event={selectedVerificationEvent}
        isOpen={!!selectedVerificationEvent}
        onClose={() => setSelectedVerificationEvent(null)}
        onConfirmVerification={handleConfirmVerification}
      />
    </div>
  );
}
