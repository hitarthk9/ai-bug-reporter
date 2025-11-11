import json
import tempfile
from jira_client import create_issues
from analysis import analyze_with_transcript
from transcript import transcribe_with_timestamps
from video import extract_audio, extract_video_clip
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Custom icon - place your icon file (icon.png, icon.ico, or icon.jpg) in the project root
# If no custom icon file exists, it will fall back to emoji
icon_path = None
project_root = os.path.dirname(os.path.abspath(__file__))
for ext in [".png", ".ico", ".jpg", ".jpeg"]:
    icon_file = os.path.join(project_root, f"icon{ext}")
    if os.path.exists(icon_file):
        icon_path = icon_file
        break

st.set_page_config(
    page_title="AI Bug Reporter",
    # Use custom icon or fallback to emoji
    page_icon=icon_path if icon_path else "🎥",
    layout="centered"
)

# Header with custom styling
st.markdown("""
    <h1 style='text-align: center;'>
        AI Bug Reporter
    <p style='text-align: center; color: #666; font-size: 0.5em; margin-top: 0; margin-bottom: 0.5em; white-space: nowrap;'>
        by Hitarth Kothari
    </p>
    <p style='text-align: center; color: #888; font-size: 0.4em; margin-top: 0; white-space: nowrap;'>
        BROWSERSTACK DEMO
    </p>
    </h1>
""", unsafe_allow_html=True)

uploaded = st.file_uploader("Upload Video", type=["mp4", "mov", "mkv"])

if uploaded:
    with st.spinner("Processing video..."):
        # Save temp video to disk
        temp_video = tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(uploaded.name)[-1])
        temp_video.write(uploaded.read())
        temp_video.flush()

        # 1 Extract audio
        audio_path = extract_audio(temp_video.name)

        # 2 Transcribe with timestamps
        segments, full_text, timestamped = transcribe_with_timestamps(
            client, audio_path)

        # 3 Analyze transcript to find bugs with time ranges
        bugs_list = analyze_with_transcript(client, timestamped)

        # 4 Extract video clips for each bug
        video_clips = {}
        if bugs_list:
            for idx, bug in enumerate(bugs_list):
                start_sec = bug.get("start_sec", 0)
                end_sec = bug.get("end_sec", start_sec + 5)

                # Add padding (±2 seconds)
                start_sec = max(0, start_sec - 2)
                end_sec = end_sec + 2

                try:
                    clip_path = extract_video_clip(
                        temp_video.name, start_sec, end_sec)
                    video_clips[idx] = clip_path
                except Exception as e:
                    st.warning(
                        f"⚠ Failed to extract clip for bug {idx+1}: {str(e)}")

        # Display results
        if bugs_list:
            st.success(
                f"✅ Found {len(bugs_list)} bug(s) and extracted {len(video_clips)} video clip(s)")

            # Display bugs in a cleaner format
            st.subheader("🧩 Detected Bugs")
            for idx, bug in enumerate(bugs_list):
                with st.container():
                    priority_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
                    priority_icon = priority_color.get(
                        bug.get("priority", "Medium"), "⚪")

                    st.markdown(
                        f"**{priority_icon} Bug {idx+1}:** {bug.get('summary', 'N/A')}")
                    st.markdown(
                        f"**Priority:** {bug.get('priority', 'Medium')}")
                    st.markdown(
                        f"**Time Range:** {bug.get('start_sec', 0):.1f}s - {bug.get('end_sec', 0):.1f}s")
                    with st.expander("View description"):
                        st.write(bug.get('description', ''))
                    st.divider()

        # Optional debug section (collapsed by default)
        with st.expander("🔍 Debug Info", expanded=False):
            st.subheader("Transcript")
            st.text(timestamped)

            st.subheader("Raw Bug Data")
            st.json(bugs_list)

            if video_clips:
                st.subheader("Video Clips")
                for idx, clip_path in video_clips.items():
                    if os.path.exists(clip_path):
                        file_size = os.path.getsize(clip_path)
                        file_size_mb = file_size / (1024 * 1024)
                        bug = bugs_list[idx]

                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{bug.get('summary', 'N/A')}**")
                            st.write(
                                f"File: `{os.path.basename(clip_path)}` | Size: {file_size_mb:.2f} MB")
                        with col2:
                            with open(clip_path, "rb") as video_file:
                                st.download_button(
                                    label="📥 Download",
                                    data=video_file.read(),
                                    file_name=f"bug_{idx+1}_{bug.get('summary', 'clip')[:30].replace(' ', '_')}.mp4",
                                    mime="video/mp4",
                                    key=f"debug_download_{idx}"
                                )

        # 5 Send to Jira with video attachments
        if bugs_list:
            jira_errors = create_issues(bugs_list, video_clips)
            if jira_errors:
                st.warning(
                    f"⚠️ {len(jira_errors)} Jira issue(s) failed to create. Check debug info for details.")
                with st.expander("View Jira errors"):
                    st.json(jira_errors)
            else:
                st.success(
                    f"✅ {len(bugs_list)} bug(s) created in Jira with video attachments!")
