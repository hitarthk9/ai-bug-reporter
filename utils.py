import os, base64

def encode_image_b64(image_path: str) -> str:
	"""Load image and return base64 data URL string."""
	with open(image_path, "rb") as f:
		b64 = base64.b64encode(f.read()).decode("utf-8")
	return "data:image/jpeg;base64," + b64

def build_second_to_frame_map(frames_dir: str) -> dict:
	"""Map second index (int starting from 1) to absolute frame path."""
	files = sorted([f for f in os.listdir(frames_dir) if f.lower().endswith(".jpg")])
	second_to_path = {}
	for idx, name in enumerate(files, start=1):
		second_to_path[idx] = os.path.join(frames_dir, name)
	return second_to_path

def get_window_images(second_to_path: dict, center_second: int, window_radius: int = 2) -> list:
	"""Get images for [center-2s, ..., center+2s] that exist."""
	images = []
	for s in range(center_second - window_radius, center_second + window_radius + 1):
		if s in second_to_path:
			images.append(second_to_path[s])
	return images

def flatten_segments_text(segments: list) -> str:
	"""Turn Whisper segments into a readable timestamped transcript.
	Handles both dict-like segments and TranscriptionSegment objects."""
	lines = []
	for seg in segments:
		# Handle both dict-like and object-like segments
		if hasattr(seg, "get"):
			# Dictionary-like access
			start_s = int(seg.get("start", 0))
			end_s = int(seg.get("end", max(start_s, 0)))
			text = seg.get("text", "").strip()
		else:
			# Object attribute access (TranscriptionSegment)
			start_s = int(getattr(seg, "start", 0))
			end_s = int(getattr(seg, "end", max(start_s, 0)))
			text = getattr(seg, "text", "").strip()
		lines.append(f"[{start_s:>3}-{end_s:>3}s] {text}")
	return "\n".join(lines)


