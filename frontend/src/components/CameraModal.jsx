import React, { useState } from 'react';
import { X, Video, Camera, Upload, Globe, Check, AlertCircle } from 'lucide-react';

export default function CameraModal({
  isOpen,
  onClose,
  cameras,
  onSelectCamera,
  onAddRtspCamera,
  onUploadVideo,
  currentCameraId
}) {
  const [activeTab, setActiveTab] = useState('demo'); // 'demo', 'upload', 'webcam', 'rtsp'
  const [rtspUrl, setRtspUrl] = useState('rtsp://admin:admin123@192.168.1.100:554/live/ch0');
  const [cameraName, setCameraName] = useState('IP Camera Highway Sector 4');
  const [cameraId, setCameraId] = useState('CAM 04');
  const [location, setLocation] = useState('North Highway Overhead');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async () => {
    if (!selectedFile) return;
    setIsSubmitting(true);
    setStatusMsg("Uploading video to AI TrafficGuard pipeline...");
    try {
      await onUploadVideo(selectedFile);
      setStatusMsg("Upload successful! Stream active.");
      setTimeout(() => {
        onClose();
        setStatusMsg(null);
      }, 1000);
    } catch (err) {
      setStatusMsg(`Upload failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRtspSubmit = async () => {
    if (!rtspUrl) return;
    setIsSubmitting(true);
    setStatusMsg("Connecting to backend RTSP stream...");
    try {
      await onAddRtspCamera({
        id: cameraId,
        name: cameraName,
        source_type: "rtsp",
        source_url: rtspUrl,
        location: location
      });
      setStatusMsg("RTSP Camera connected successfully!");
      setTimeout(() => {
        onClose();
        setStatusMsg(null);
      }, 1000);
    } catch (err) {
      setStatusMsg(`RTSP connection failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const sampleVideos = [
    { id: "CAM 01", name: "Overhead Highway AR2 (Primary CCTV)", path: "cctv_camera_feed.mp4", loc: "Ayesha Buni Sh Faisal AR2" },
    { id: "CAM 02", name: "Downtown North Intersection", path: "traffic_real_life_1.mp4", loc: "North Boulevard 04" },
    { id: "CAM 03", name: "Toll Plaza Inbound Corridor", path: "sample_feed_raw.mp4", loc: "Plaza Checkpoint E" }
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono select-none">
      <div className="w-full max-w-2xl bg-[#0b0f17] border border-[#222e40] rounded-sm shadow-2xl overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1f2a3a] bg-[#0e141f]">
          <div className="flex items-center space-x-2">
            <Camera size={16} className="text-amber-400" />
            <span className="font-bold text-sm text-[#e2e8f0]">SURVEILLANCE CAMERA & SOURCE CONFIGURATION</span>
          </div>
          <button 
            onClick={onClose}
            className="text-[#64748b] hover:text-[#e2e8f0] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[#1f2a3a] bg-[#080b0f] text-xs">
          <button
            onClick={() => setActiveTab('demo')}
            className={`flex-1 py-2.5 px-3 flex items-center justify-center space-x-1.5 transition-colors border-b-2 ${
              activeTab === 'demo' ? 'border-amber-400 text-amber-400 bg-[#121926]' : 'border-transparent text-[#64748b] hover:text-[#94a3b8]'
            }`}
          >
            <Video size={14} />
            <span>DEMO CCTV VIDEOS</span>
          </button>

          <button
            onClick={() => setActiveTab('upload')}
            className={`flex-1 py-2.5 px-3 flex items-center justify-center space-x-1.5 transition-colors border-b-2 ${
              activeTab === 'upload' ? 'border-amber-400 text-amber-400 bg-[#121926]' : 'border-transparent text-[#64748b] hover:text-[#94a3b8]'
            }`}
          >
            <Upload size={14} />
            <span>UPLOAD MP4</span>
          </button>

          <button
            onClick={() => setActiveTab('rtsp')}
            className={`flex-1 py-2.5 px-3 flex items-center justify-center space-x-1.5 transition-colors border-b-2 ${
              activeTab === 'rtsp' ? 'border-amber-400 text-amber-400 bg-[#121926]' : 'border-transparent text-[#64748b] hover:text-[#94a3b8]'
            }`}
          >
            <Globe size={14} />
            <span>LIVE RTSP IP CAM</span>
          </button>

          <button
            onClick={() => setActiveTab('webcam')}
            className={`flex-1 py-2.5 px-3 flex items-center justify-center space-x-1.5 transition-colors border-b-2 ${
              activeTab === 'webcam' ? 'border-amber-400 text-amber-400 bg-[#121926]' : 'border-transparent text-[#64748b] hover:text-[#94a3b8]'
            }`}
          >
            <Camera size={14} />
            <span>WEBCAM</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 space-y-4 text-xs">
          {/* TAB 1: DEMO VIDEOS */}
          {activeTab === 'demo' && (
            <div className="space-y-3">
              <p className="text-[#94a3b8]">Select from pre-calibrated city traffic CCTV surveillance feeds:</p>
              <div className="space-y-2">
                {sampleVideos.map((cam) => {
                  const isActive = currentCameraId === cam.id;
                  return (
                    <div
                      key={cam.id}
                      onClick={() => {
                        onSelectCamera(cam);
                        onClose();
                      }}
                      className={`flex items-center justify-between p-3 border rounded-sm cursor-pointer transition-all ${
                        isActive 
                          ? 'bg-amber-950/30 border-amber-500 text-amber-300' 
                          : 'bg-[#0f1521] border-[#1e2736] hover:border-[#38bdf8] text-[#e2e8f0]'
                      }`}
                    >
                      <div className="flex flex-col">
                        <span className="font-bold text-sm">{cam.id} - {cam.name}</span>
                        <span className="text-[10px] text-[#64748b]">{cam.loc}</span>
                      </div>
                      {isActive && <Check size={18} className="text-amber-400" />}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: UPLOAD CUSTOM MP4 */}
          {activeTab === 'upload' && (
            <div className="space-y-4">
              <p className="text-[#94a3b8]">Upload your own CCTV footage (.mp4) to test live detection and violation logging:</p>
              <div className="border-2 border-dashed border-[#233145] hover:border-[#00e5ff] rounded p-6 flex flex-col items-center justify-center space-y-2 bg-[#090e16] transition-colors cursor-pointer">
                <input 
                  type="file" 
                  accept="video/mp4,video/avi,video/mkv" 
                  onChange={handleFileChange}
                  className="hidden" 
                  id="mp4-upload" 
                />
                <label htmlFor="mp4-upload" className="cursor-pointer flex flex-col items-center">
                  <Upload size={32} className="text-[#00e5ff] mb-2" />
                  <span className="text-sm font-semibold text-white">
                    {selectedFile ? selectedFile.name : "Click to select MP4 video file"}
                  </span>
                  <span className="text-[10px] text-[#64748b] mt-1">Recommended: H.264 MP4 1080p or 720p</span>
                </label>
              </div>

              <button
                disabled={!selectedFile || isSubmitting}
                onClick={handleUploadSubmit}
                className="w-full py-2.5 bg-[#00e5ff] hover:bg-[#00c4dc] disabled:bg-[#1e293b] text-black font-bold uppercase tracking-wider rounded-sm transition-colors"
              >
                {isSubmitting ? "Processing Upload..." : "Load Video Into Pipeline"}
              </button>
            </div>
          )}

          {/* TAB 3: RTSP IP CAMERA */}
          {activeTab === 'rtsp' && (
            <div className="space-y-3">
              <div className="p-2.5 bg-blue-950/30 border border-blue-800/40 rounded text-blue-200 text-[11px] leading-relaxed">
                Connects directly to your IP Camera or NVR via the Python FastAPI backend. The backend handles RTSP decoding via OpenCV/FFmpeg and streams detections to the web client.
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#64748b] uppercase block mb-1">Camera ID</label>
                  <input
                    type="text"
                    value={cameraId}
                    onChange={(e) => setCameraId(e.target.value)}
                    className="w-full bg-[#080b0f] border border-[#232e3f] p-2 text-white rounded-sm focus:border-[#00e5ff] outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#64748b] uppercase block mb-1">Location Label</label>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    className="w-full bg-[#080b0f] border border-[#232e3f] p-2 text-white rounded-sm focus:border-[#00e5ff] outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-[#64748b] uppercase block mb-1">Camera Name</label>
                <input
                  type="text"
                  value={cameraName}
                  onChange={(e) => setCameraName(e.target.value)}
                  className="w-full bg-[#080b0f] border border-[#232e3f] p-2 text-white rounded-sm focus:border-[#00e5ff] outline-none"
                />
              </div>

              <div>
                <label className="text-[10px] text-[#64748b] uppercase block mb-1">RTSP Stream URL</label>
                <input
                  type="text"
                  value={rtspUrl}
                  onChange={(e) => setRtspUrl(e.target.value)}
                  placeholder="rtsp://user:pass@192.168.1.100:554/stream1"
                  className="w-full bg-[#080b0f] border border-[#232e3f] p-2 text-[#00e5ff] rounded-sm focus:border-[#00e5ff] outline-none"
                />
              </div>

              <button
                disabled={isSubmitting || !rtspUrl}
                onClick={handleRtspSubmit}
                className="w-full py-2.5 bg-amber-500 hover:bg-amber-400 disabled:bg-[#1e293b] text-black font-bold uppercase tracking-wider rounded-sm transition-colors mt-2"
              >
                {isSubmitting ? "Connecting..." : "Connect IP Camera"}
              </button>
            </div>
          )}

          {/* TAB 4: WEBCAM */}
          {activeTab === 'webcam' && (
            <div className="space-y-4">
              <p className="text-[#94a3b8]">Ingest direct video from local USB camera or integrated webcam:</p>
              <button
                onClick={() => {
                  onSelectCamera({ id: "CAM 01", name: "Local Webcam Input", path: "0", loc: "Local Testing Rig", source_type: "webcam" });
                  onClose();
                }}
                className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-black font-bold uppercase tracking-wider rounded-sm transition-colors"
              >
                Engage Default Webcam (Camera Index 0)
              </button>
            </div>
          )}

          {/* Feedback Status */}
          {statusMsg && (
            <div className="p-2 bg-[#141b24] border border-[#232f40] rounded text-center text-xs text-[#00e5ff]">
              {statusMsg}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
