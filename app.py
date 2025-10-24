import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pandas as pd
import isodate

# ====== UI 設定 ======
st.set_page_config(page_title="YouTube Shorts 熱門搜尋器", layout="wide")
st.title("🎬 YouTube Shorts 熱門搜尋器（Streamlit 版）")

# ====== 快取 YouTube 服務物件 ======
@st.cache_resource
def get_youtube_service(api_key):
    return build('youtube', 'v3', developerKey=api_key)

# ====== 快取影片類別 ======
@st.cache_data(show_spinner=False)
def get_video_categories(api_key, region_code='TW'):
    youtube = get_youtube_service(api_key)
    categories_response = youtube.videoCategories().list(
        part='snippet',
        regionCode=region_code
    ).execute()
    categories = {}
    for item in categories_response['items']:
        categories[item['id']] = item['snippet']['title']
    return categories

# ====== 工具函數 ======
def get_time_filter(hours):
    if hours == "all":
        return None
    published_after = datetime.utcnow() - timedelta(hours=int(hours))
    return published_after.strftime('%Y-%m-%dT%H:%M:%SZ')

def format_duration(duration):
    try:
        parsed_duration = isodate.parse_duration(duration)
        total_seconds = int(parsed_duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except:
        return duration

def get_duration_seconds(duration):
    try:
        parsed_duration = isodate.parse_duration(duration)
        return int(parsed_duration.total_seconds())
    except:
        return 0

# ====== Sidebar 搜尋條件 ======
with st.sidebar:
    st.header("API Key 設定")
    api_key = st.text_input("請輸入 YouTube API Key", type="password", help="需啟用 YouTube Data API v3")
    st.markdown("[如何取得 API Key?](https://console.cloud.google.com/)")

    st.header("搜尋條件")
    keyword = st.text_input("關鍵字", value="shorts", help="留空使用 shorts")
    category_filter = st.selectbox("影片類別", options=[
        ("all", "不限制"),
        ("1", "電影與動畫"),
        ("2", "汽車與交通工具"),
        ("10", "音樂"),
        ("15", "寵物與動物"),
        ("17", "體育"),
        ("19", "旅遊與活動"),
        ("20", "遊戲"),
        ("22", "人物與部落格"),
        ("23", "喜劇"),
        ("24", "娛樂"),
        ("25", "新聞與政治"),
        ("26", "操作說明與風格"),
        ("27", "教育"),
        ("28", "科學與技術")
    ], index=0, format_func=lambda x: x[1])[0]
    region_filter = st.selectbox("地區", [
        "TW", "US", "JP", "KR", "CN", "HK", "SG", "IN", "GB", "DE", "FR", "NO", "CH", "DK", "AE", "SA", "MX", "CA", "AU", "RU"
    ], index=0)
    time_filter = st.selectbox("上傳時間", [("all", "不限制"), ("6", "6小時內"), ("12", "12小時內"), ("24", "24小時內")], index=3, format_func=lambda x: x[1])[0]
    min_views = st.number_input("最少觀看次數", min_value=0, value=10000, step=1000)
    max_duration = st.selectbox("影片長度（秒）", [
        ("all", "不限制"), ("5", "≤ 5"), ("10", "≤ 10"), ("15", "≤ 15"), ("30", "≤ 30"), ("60", "≤ 60"),
        ("90", "≤ 90"), ("120", "≤ 120"), ("180", "≤ 180")
    ], index=5, format_func=lambda x: x[1])[0]
    max_results = st.selectbox("結果數量", [10, 25, 50], index=1)

    st.markdown("---")
    search_btn = st.button("🔍 搜尋影片")

# ====== 搜尋並顯示結果 ======
if search_btn:
    if not api_key or len(api_key) < 20:
        st.error("請先輸入有效的 YouTube Data API Key。")
        st.stop()
    try:
        youtube = get_youtube_service(api_key)
        categories = get_video_categories(api_key, region_code=region_filter)
        st.success(f"成功取得 API 與類別（共 {len(categories)} 個類別）")
    except Exception as e:
        st.error(f"API Key 錯誤或無法連線: {e}")
        st.stop()

    # 準備搜尋參數
    q = keyword.strip() if keyword.strip() else "shorts"
    search_params = {
        "part": "snippet",
        "q": q,
        "type": "video",
        "order": "relevance",
        "maxResults": min(50, max_results * 3),
        "regionCode": region_filter
    }
    lang_map = {"TW": "zh", "CN": "zh", "HK": "zh", "SG": "zh", "JP": "ja", "KR": "ko", "NO": "no", "CH": "de", "DE": "de", "DK": "da", "AE": "ar", "SA": "ar", "US": "en", "GB": "en", "CA": "en", "AU": "en", "IN": "en", "FR": "fr", "RU": "ru"}
    if region_filter in lang_map:
        search_params["relevanceLanguage"] = lang_map[region_filter]
    if category_filter != "all":
        search_params["videoCategoryId"] = category_filter
    if time_filter != "all":
        published_after = get_time_filter(time_filter)
        if published_after:
            search_params["publishedAfter"] = published_after

    # ====== 搜尋影片 ======
    with st.spinner("正在搜尋影片..."):
        try:
            search_response = youtube.search().list(**search_params).execute()
        except Exception as e:
            st.error(f"搜尋失敗: {e}")
            st.stop()

    all_video_ids = []
    seen_ids = set()
    for item in search_response.get("items", []):
        video_id = item["id"]["videoId"]
        if video_id not in seen_ids:
            all_video_ids.append(video_id)
            seen_ids.add(video_id)

    # 下一頁（如有需要）
    while len(all_video_ids) < min(max_results * 2, 50) and "nextPageToken" in search_response:
        search_params["pageToken"] = search_response["nextPageToken"]
        search_response = youtube.search().list(**search_params).execute()
        for item in search_response.get("items", []):
            video_id = item["id"]["videoId"]
            if video_id not in seen_ids and len(all_video_ids) < 50:
                all_video_ids.append(video_id)
                seen_ids.add(video_id)
        if len(all_video_ids) >= 50:
            break

    # 取得影片詳細資料
    batch_size = 50
    all_video_items = []
    for i in range(0, len(all_video_ids), batch_size):
        batch_ids = all_video_ids[i:i + batch_size]
        try:
            videos_response = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch_ids)
            ).execute()
            all_video_items.extend(videos_response.get("items", []))
        except Exception as e:
            st.warning(f"部份影片詳情查詢失敗: {e}")

    # 組裝結果
    videos = []
    for item in all_video_items:
        video_data = item["snippet"]
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})
        view_count = int(statistics.get("viewCount", 0))
        if view_count < min_views:
            continue
        if max_duration != "all":
            duration_seconds = get_duration_seconds(content_details.get("duration", ""))
            if duration_seconds > int(max_duration):
                continue
        category_id = video_data.get("categoryId", "")
        category_name = categories.get(category_id, f'未知類別 ({category_id})')
        video_info = {
            "影片ID": item["id"],
            "影片標題": video_data["title"],
            "頻道名稱": video_data.get("channelTitle", ""),
            "頻道ID": video_data.get("channelId", ""),
            "影片類別": category_name,
            "上傳時間": video_data.get("publishedAt", ""),
            "觀看次數": view_count,
            "按讚數": int(statistics.get("likeCount", 0)),
            "留言數": int(statistics.get("commentCount", 0)),
            "影片長度": format_duration(content_details.get("duration", "")),
            "畫質": content_details.get("definition", ""),
            "字幕": "有" if content_details.get("caption", "") == "true" else "無",
            "授權內容": "是" if content_details.get("licensedContent", False) else "否",
            "影片連結": f"https://www.youtube.com/watch?v={item['id']}",
            "影片描述": video_data.get("description", "")[:500],
            "標籤": ", ".join(video_data.get("tags", [])) if video_data.get("tags") else "無",
            "縮圖": video_data.get("thumbnails", {}).get("medium", {}).get("url", "")
        }
        videos.append(video_info)

    videos.sort(key=lambda x: x["觀看次數"], reverse=True)
    videos = videos[:max_results]

    st.subheader("搜尋結果")
    if not videos:
        st.warning("找不到符合條件的影片，請試試調整條件。")
    else:
        for v in videos:
            colL, colR = st.columns([1, 4])
            with colL:
                if v["縮圖"]:
                    st.image(v["縮圖"], width=170)
            with colR:
                st.markdown(f"**[{v['影片標題']}]({v['影片連結']})**")
                st.write(f"頻道：{v['頻道名稱']}　|　類別：{v['影片類別']}　|　{v['影片長度']}　|　{v['觀看次數']}次")
                st.caption(v["影片描述"])
            st.divider()

        # 匯出 CSV
        csv_df = pd.DataFrame(videos)
        csv_bytes = csv_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📥 匯出 CSV",
            data=csv_bytes,
            file_name=f"YouTube_shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
