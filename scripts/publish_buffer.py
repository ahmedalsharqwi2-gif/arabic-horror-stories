"""نشر أصول الحلقة الجديدة عبر Buffer.

الترتيب:
- الفيديو الكامل الأفقي.
- ريل واحد فقط (مأخوذ من أول الحلقة)، ينشر في نفس لحظة الفيديو الكامل
  (نفس FULL_VIDEO_DELAY_HOURS) بدل ما يتأخر عنه — الاتنين ينشروا مع بعض.


لا يوجد هنا منطق part1/part2. كل أصل يرفع وينشر Native على كل قناة.

=== إصلاح جديد (يوتيوب / انستجرام) ===
1) يوتيوب: Buffer's `YoutubePostMetadataInput` ليس فيه حقل `type` إطلاقًا
   (تأكدنا من توثيق Buffer الرسمي على developers.buffer.com). حقل `type`
   موجود بس في نوع الـ output (`YoutubePostMetadata`) اللي بيوصف حالة
   البوست بعد النشر، مش نوع الـ input اللي بنستخدمه وقت الإنشاء. إرساله
   كان بيرجّع "Field 'type' is not defined by type 'YoutubePostMetadataInput'"
   لكل الأصول (الفيديو الكامل + الريل) بنفس الرسالة بالظبط. الحل: حذف
   الحقل من فرع يوتيوب خالص. يوتيوب بيحدد تلقائيًا لو الفيديو "Short" من
   مواصفات الملف نفسه (نسبة أبعاد رأسية/مربعة + مدة قصيرة)، مش من أي حقل
   بتبعته لـ Buffer.
2) انستجرام: `InstagramPostMetadataInput.type` حقل `PostType!` إلزامي،
   وقيمه المسموحة (enum PostType) هي: post, reel, story, short, carousel,
   event, offer, ghost_post, thread, whats_new — القيمة "video" مش من
   ضمنهم، فكانت هترجع خطأ enum مشابه لو اتبعتت فعلًا. الحل: "post"
   للفيديو الكامل (فيديو Feed عادي)، و"reel" للريل (زي ما هو).
3) انستجرام كان مش بيتنشرله خالص (ولا حتى محاولة فاشلة في اللوج) لأن
   channel_ids() كانت بتعتمد على متغير BUFFER_CHANNEL_ID المنفصل، ولو
   القيمة دي متظبطة يدويًا وناقص منها معرّف انستجرام، بيرجع بس يوتيوب/
   فيسبوك ويتجاهل انستجرام بصمت تام من غير أي رسالة خطأ. الحل: channel_ids()
   بقت تعتمد دايمًا على CHANNEL_SERVICES (المبني من BUFFER_YOUTUBE_CHANNEL_ID
   / BUFFER_FACEBOOK_CHANNEL_ID / BUFFER_INSTAGRAM_CHANNEL_ID مباشرة)، بدل
   القائمة المجمّعة القديمة اللي ممكن تفضل من غير تحديث. لسه لازم تتأكد إن
   BUFFER_INSTAGRAM_CHANNEL_ID نفسه متظبط في GitHub Secrets بمعرّف قناة
   انستجرام الصحيح — لو الـ secret ده مش موجود أصلًا، مفيش كود يقدر يعوّض
   عنه.
4) يوتيوب كان بيرفض الفيديو الكامل برسالة:
   "Video must be no longer than 3 minutes for YouTube Shorts." +
   "Video must be vertical (portrait orientation) for YouTube Shorts."
   رغم إن الفيديو أفقي فعلًا (تم التأكد من أبعاده قبل الرفع). السبب:
   وجود هاشتاج #Shorts/#Short جوه نص البوست (منقول من caption الحلقة،
   اللي بيتشارك بين الفيديو الكامل والريل) بيخلي يوتيوب يحاول يصنّف
   الفيديو تلقائيًا كـ Short بغض النظر عن أبعاده الحقيقية، فيرفضه لما
   يفشل شروط الـ Shorts. الحل: دالة strip_shorts_hashtag() بتشيل أي
   هاشتاج #Shorts/#Short من نص البوست الخاص بالفيديو الكامل تحديدًا
   (caption + hashtags المجمّعة) قبل إرساله لـ Buffer.

=== تحديث الجدولة (ريل واحد بدل اتنين) ===
كان فيه short_1 و short_2 بفارق زمني بينهم وبين الفيديو الكامل. دلوقتي
assemble_video.py بينتج ريل واحد بس (مأخوذ من أول الحلقة)، وده بينشر في
نفس لحظة الفيديو الكامل (نفس FULL_VIDEO_DELAY_HOURS) بدل ما يتأخر عنه —
عشان الاتنين يوصلوا الجمهور مع بعض الساعة اللي محددها المستخدم (~7م).
متغيرات FULL_TO_SHORT_1_HOURS / FULL_TO_SHORT_2_HOURS اتشالت خالص —
لم يعد هناك حاجة لهم.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
EPISODE_PATH = ROOT_DIR / "state" / "current_episode.json"
OUTPUT_DIR = ROOT_DIR / "output"
BUFFER_GRAPHQL_API = "https://api.buffer.com"
GITHUB_API = "https://api.github.com"
RELEASE_TAG = "media-assets"
CHANNEL_PENDING_LIMIT = int(os.environ.get("CHANNEL_PENDING_LIMIT", "10"))
ENABLE_PREFLIGHT_CHECK = os.environ.get("ENABLE_PREFLIGHT_CHECK", "true").lower() != "false"

# الفيديو الكامل (طويل) أداؤه أفضل مساءً لما المشاهد يكون عنده وقت فراغ
# فعلي. القيمة الافتراضية هنا بتفترض تشغيل الـ workflow صباحًا وتؤجل
# النشر الفعلي لنفس اليوم مساءً؛ لو غيّرت معاد الـ cron، اضبط القيمة دي
# معاه. الريل الوحيد بيستخدم نفس القيمة بالظبط عشان ينشر مع الفيديو
# الكامل في نفس اللحظة.
FULL_VIDEO_DELAY_HOURS = float(os.environ.get("FULL_VIDEO_DELAY_HOURS", "0"))

def publish_target_utc(hour: int = 19) -> datetime:
    """Return the next 19:00 Africa/Cairo converted to UTC.
    This is absolute scheduling, so SILMA duration does not shift the post.
    """
    now = datetime.now(timezone.utc)
    cairo = now.astimezone(ZoneInfo("Africa/Cairo"))
    target = cairo.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= cairo:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)


def scheduled_publish_utc(default_hour: int = 19) -> datetime:
    """Use the workflow's exact final slot when one was computed."""
    raw = os.environ.get("PUBLISH_DUE_AT", "").strip()
    if raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("PUBLISH_DUE_AT must include a timezone")
        return parsed.astimezone(timezone.utc)
    return publish_target_utc(default_hour)



# يوتيوب بيعامل أي فيديو نصّه فيه #Shorts/#Short كـ Short تلقائيًا بغض النظر
# عن أبعاده الحقيقية. لازم نشيله من نص الفيديو الكامل حتى لا يُرفض برسالة
# "Video must be no longer than 3 minutes / must be vertical for YouTube Shorts".
SHORTS_HASHTAG_RE = re.compile(r"(?<!\w)#[Ss]hort[s]?\b")
DEFAULT_HASHTAGS = ("#رعب", "#قصص_رعب", "#غموض")


def strip_shorts_hashtag(text: str) -> str:
    """يشيل أي هاشتاج #Shorts/#Short من نص الفيديو الكامل حتى لا يصنّفه
    يوتيوب تلقائيًا كـ Short (سلوك معروف: وجود #Shorts في الوصف بيخلي
    يوتيوب يحاول يعامل الفيديو كـ Short بغض النظر عن أبعاده الحقيقية)،
    فيرفض الرفع بالخطأين:
    "Video must be no longer than 3 minutes for YouTube Shorts."
    "Video must be vertical (portrait orientation) for YouTube Shorts."
    """
    return SHORTS_HASHTAG_RE.sub("", text).strip()


def ensure_caption_hashtags(title: str, caption: str) -> str:
    """Never publish an empty caption or a post without relevant hashtags."""
    text = " ".join(str(caption or "").split()).strip() or str(title).strip()
    existing = re.findall(r"(?<!\w)#[\w\u0600-\u06FF]+", text)
    tags = list(dict.fromkeys(existing + list(DEFAULT_HASHTAGS)))[:5]
    return f"{text}\n\n{' '.join(tags)}".strip()


def build_channel_services() -> dict[str, str]:
    result = {}
    for env_name, service in {
        "BUFFER_YOUTUBE_CHANNEL_ID": "youtube",
        "BUFFER_FACEBOOK_CHANNEL_ID": "facebook",
        "BUFFER_INSTAGRAM_CHANNEL_ID": "instagram",
    }.items():
        value = os.environ.get(env_name, "").strip()
        if value:
            result[value] = service
    return result


CHANNEL_SERVICES = build_channel_services()

CREATE_POST_MUTATION = """
mutation CreatePost($text: String!, $channelId: ChannelId!, $videoUrl: String!, $metadata: PostInputMetaData, $dueAt: DateTime!) {
  createPost(input: {
    text: $text
    channelId: $channelId
    schedulingType: automatic
    mode: customScheduled
    dueAt: $dueAt
    metadata: $metadata
    assets: [{ video: { url: $videoUrl } }]
  }) {
    ... on PostActionSuccess { post { id text dueAt } }
    ... on MutationError { message }
  }
}
"""
GET_ORGANIZATIONS_QUERY = "query GetOrganizations { account { organizations { id name } } }"
GET_PENDING_QUERY = """
query GetPendingPosts($organizationId: OrganizationId!, $channelId: ChannelId!) {
  posts(first: 10, input: {organizationId: $organizationId, filter: {status: [scheduled], channelIds: [$channelId]}}) {
    edges { node { id } }
  }
}
"""


def graphql(query: str, variables: dict, api_key: str) -> dict:
    response = requests.post(
        BUFFER_GRAPHQL_API,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"query": query, "variables": variables},
        timeout=40,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"]))
    return data.get("data", {})


def github_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def upload_media(video_path: Path, token: str) -> str:
    repo = os.environ.get("MEDIA_REPOSITORY") or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("MEDIA_REPOSITORY أو GITHUB_REPOSITORY غير موجود.")
    release_response = requests.get(f"{GITHUB_API}/repos/{repo}/releases/tags/{RELEASE_TAG}", headers=github_headers(token), timeout=20)
    if release_response.status_code == 404:
        release_response = requests.post(
            f"{GITHUB_API}/repos/{repo}/releases",
            headers=github_headers(token),
            json={"tag_name": RELEASE_TAG, "name": "Media Assets", "body": "Temporary hosting for Buffer assets.", "prerelease": True},
            timeout=20,
        )
    release_response.raise_for_status()
    release = release_response.json()
    asset_name = f"video_{video_path.stem}_{os.environ.get('GITHUB_RUN_ID', 'local')}.mp4"
    with video_path.open("rb") as handle:
        response = requests.post(
            release["upload_url"].split("{")[0], headers={**github_headers(token), "Content-Type": "video/mp4"},
            params={"name": asset_name}, data=handle, timeout=300,
        )
    response.raise_for_status()
    return response.json()["browser_download_url"]


def video_dimensions(video_path: Path) -> tuple[int, int]:
    """يقرأ أبعاد الفيديو قبل رفعه حتى لا يصل الكامل إلى YouTube كـShort."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0:s=x", str(video_path)],
        capture_output=True, text=True, check=False,
    )
    try:
        width, height = result.stdout.strip().split("x", 1)
        return int(width), int(height)
    except (ValueError, AttributeError):
        raise RuntimeError(f"تعذر قراءة أبعاد الفيديو: {video_path}")


def metadata_for(channel_id: str, asset_type: str, title: str) -> dict | None:
    service = CHANNEL_SERVICES.get(channel_id)
    if service == "youtube":
        # لا نرسل isAiGenerated=true تلقائيًا ولا نضع نصًا يعلن ذلك؛ هذا الحقل
        # إفصاح رسمي وليس وسمًا شكليًا. إذا كان مطلوبًا في حسابك، أضفه صراحةً
        # عبر إعداد مستقل بعد مراجعة سياسة YouTube.
        # ملحوظة: بدون "type" — YoutubePostMetadataInput مفيهوش الحقل ده
        # أصلًا (شوف الشرح في أعلى الملف).
        return {"youtube": {
            "title": title[:100] or "Horror Episode",
            "categoryId": "24",
            "privacy": "public",
            "madeForKids": False,
            "notifySubscribers": asset_type == "full_video",
        }}
    if service == "facebook":
        # قيم Facebook الرسمية هي post / reel / story؛ لا توجد قيمة video.
        return {"facebook": {"type": "reel"}}
    if service == "instagram":
        # كل الفيديوهات (الكامل والريل) بتتبعت كـ"reel" — لا "post"،
        # لأن نوع "post" عند Buffer بيفرض حد قديم 60 ثانية لفيديوهات
        # Instagram (رسالة الخطأ: "Video must be no longer than 1 minute
        # for Instagram Posts")، بينما Instagram Graph API الرسمي بيسمح
        # بحد 15 دقيقة (900 ثانية) لـReels — والفيديو الكامل (~6 دقايق)
        # داخل الحد ده براحة. shouldShareToFeed=True بيخلي الـreel يظهر
        # في الـFeed العادي كمان زي منشور فيديو تقليدي.
        return {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    return None


def build_post_text(service: str, asset_type: str, title: str, caption: str, full_url: str | None = None) -> str:
    caption = ensure_caption_hashtags(title, caption)
    hashtags = " ".join(dict.fromkeys(re.findall(r"(?<!\w)#\S+", caption)))
    if asset_type == "full_video":
        # مهم: نشيل #Shorts/#Short من كابشن ومن الهاشتاجات المجمّعة للفيديو
        # الكامل، وإلا يوتيوب هيحاول يصنّفه Short ويرفضه لأنه أفقي وأطول
        # من 3 دقايق (شوف strip_shorts_hashtag بالتفصيل في أعلى الملف).
        clean_caption = strip_shorts_hashtag(caption)
        clean_hashtags = strip_shorts_hashtag(hashtags)
        parts = [title.strip(), clean_caption.strip()]
        if clean_hashtags and clean_hashtags not in "\n".join(parts):
            parts.append(clean_hashtags)
        return "\n\n".join(part for part in parts if part).strip()
    elif service == "youtube":
        parts = [f"{title.strip()} — مقتطف", "عايز تشوف باقي الحلقة؟ شاهدها كاملة على YouTube."]
        if full_url:
            parts.append(f"🔗 الحلقة الكاملة: {full_url}")
    elif service == "facebook":
        parts = [f"{title.strip()} — مقتطف", "عايز تشوف باقي الحلقة؟ شاهدها كاملة على صفحتنا."]
        if full_url:
            parts.append(f"🔗 الحلقة الكاملة: {full_url}")
    else:
        parts = [f"{title.strip()} — مقتطف", "عايز تشوف باقي الحلقة؟ الحلقة كاملة على صفحتنا."]
    if hashtags and hashtags not in "\n".join(parts):
        parts.append(hashtags)
    return "\n\n".join(part for part in parts if part).strip()


def iso_after(hours: float) -> str:
    due = scheduled_publish_utc(19)
    return due.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def organization_id(api_key: str) -> str:
    organizations = graphql(GET_ORGANIZATIONS_QUERY, {}, api_key).get("account", {}).get("organizations", [])
    if not organizations:
        raise RuntimeError("لم يتم العثور على Buffer organization.")
    return organizations[0]["id"]


def pending_count(org_id: str, channel_id: str, api_key: str) -> int:
    data = graphql(GET_PENDING_QUERY, {"organizationId": org_id, "channelId": channel_id}, api_key)
    return len(data.get("posts", {}).get("edges", []))


def create_post(video_url: str, text: str, title: str, channel_id: str, api_key: str, due_at: str, asset_type: str) -> dict:
    variables = {"text": text, "channelId": channel_id, "videoUrl": video_url, "metadata": metadata_for(channel_id, asset_type, title), "dueAt": due_at}
    data = graphql(CREATE_POST_MUTATION, variables, api_key)
    result = data.get("createPost") or {}
    if result.get("message"):
        raise RuntimeError(result["message"])
    if not result.get("post"):
        raise RuntimeError(f"لم يُرجع Buffer منشورًا: {result}")
    return result["post"]


def channel_ids() -> list[str]:
    # بقت دايمًا بترجع كل القنوات المعرّفة فعليًا (من BUFFER_YOUTUBE_CHANNEL_ID
    # / BUFFER_FACEBOOK_CHANNEL_ID / BUFFER_INSTAGRAM_CHANNEL_ID) بدل ما تعتمد
    # على BUFFER_CHANNEL_ID المنفصل، اللي كان ممكن يفضل من غير تحديث ويستبعد
    # قناة زي انستجرام بصمت تام من غير أي رسالة خطأ في اللوج.
    return list(CHANNEL_SERVICES.keys())


def _run() -> None:
    api_key = os.environ.get("BUFFER_API_KEY", "").strip()
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not api_key or not github_token:
        raise RuntimeError("BUFFER_API_KEY و GITHUB_TOKEN مطلوبان.")
    if not EPISODE_PATH.exists():
        raise RuntimeError("state/current_episode.json غير موجود.")

    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    title = str(episode.get("title", "Horror Episode")).strip()
    caption = str(episode.get("caption", "")).strip() or title

    full_path = OUTPUT_DIR / "final_video_full.mp4"
    if not full_path.exists() or full_path.stat().st_size == 0:
        raise RuntimeError(f"الفيديو الكامل غير موجود: {full_path}")
    full_width, full_height = video_dimensions(full_path)
    if full_width * 16 != full_height * 9:
        raise RuntimeError(f"الفيديو الكامل يجب أن يكون عموديًا 9:16 ({full_width}x{full_height}).")
    print(f"✅ الفيديو الكامل العمودي: {full_width}x{full_height}")

    shorts = sorted(OUTPUT_DIR.glob("short_*_*.mp4"))
    if not shorts:
        raise RuntimeError("لا يوجد ريل جاهز للنشر.")
    # ترتيب ثابت حسب المنصة.
    shorts = sorted(shorts, key=lambda p: (int(p.stem.split("_")[1]), p.stem))

    ids = channel_ids()
    if not ids:
        raise RuntimeError(
            "لا يوجد أي قناة معرّفة: تأكد إن BUFFER_YOUTUBE_CHANNEL_ID / "
            "BUFFER_FACEBOOK_CHANNEL_ID / BUFFER_INSTAGRAM_CHANNEL_ID متظبطين "
            "في GitHub Secrets."
        )
    missing_services = {"youtube", "facebook", "instagram"} - set(CHANNEL_SERVICES.values())
    if missing_services:
        print(
            "⚠️ القنوات دي مفيش لها معرّف قناة متظبط في GitHub Secrets وهتتخطى "
            "بالكامل: " + ", ".join(sorted(missing_services))
        )

    org_id = organization_id(api_key) if ENABLE_PREFLIGHT_CHECK else None
    services = {cid: CHANNEL_SERVICES[cid] for cid in ids}
    full_urls = {}
    for service in set(services.values()):
        full_urls[service] = os.environ.get(f"FULL_VIDEO_URL_{service.upper()}", "").strip() or None

    # كل الأصول (الفيديو الكامل + الريل على كل منصة) بتستخدم نفس التأخير
    # FULL_VIDEO_DELAY_HOURS، عشان تُنشر كلها مع بعض في نفس اللحظة.
    assets: list[tuple[str, Path]] = [("full_video", full_path)]
    for path in shorts:
        assets.append(("short", path))

    successes = 0
    failures = []
    for asset_type, path in assets:
        platform_hint = path.stem.rsplit("_", 1)[-1] if asset_type == "short" else None
        if platform_hint and platform_hint not in services.values():
            # ملهاش قناة معرّفة أصلًا (زي انستجرام لو الـ secret ناقص) —
            # نتخطى رفع الملف نفسه بدل ما نرفعه لـ GitHub من غير أي
            # وجهة نشر، وده كان بيظهر كسطر "📤" مُضلّل بيوحي بنجاح.
            print(f"⏭️  {path.name}: تخطي — لا توجد قناة {platform_hint} معرّفة (لم يُرفع الملف)")
            continue
        url = upload_media(path, github_token)
        due_at = iso_after(FULL_VIDEO_DELAY_HOURS)
        print(f"📤 {path.name} → {due_at} UTC")
        for cid in ids:
            service = services[cid]
            if platform_hint and platform_hint != service:
                continue
            if asset_type == "full_video" and service == "youtube":
                # Buffer لا يدعم فيديوهات يوتيوب الطويلة (Long-form) إطلاقًا،
                # يدعم Shorts فقط. الفيديو الكامل بيتنشر ليوتيوب بشكل منفصل
                # عبر scripts/publish_youtube_direct.py باستخدام YouTube Data
                # API مباشرة، فبنتخطى محاولته هنا بدل ما يفشل دايمًا برسالة
                # "Video must be no longer than 3 minutes / must be vertical
                # for YouTube Shorts".
                print("  ⏭️  youtube: يُنشر بشكل منفصل عبر publish_youtube_direct.py (تم التخطي هنا)")
                continue
            try:
                if org_id is not None and pending_count(org_id, cid, api_key) >= CHANNEL_PENDING_LIMIT:
                    raise RuntimeError(f"قائمة Buffer ممتلئة ({CHANNEL_PENDING_LIMIT}) للقناة {service}")
                text = build_post_text(service, asset_type, title, caption, full_urls.get(service))
                post = create_post(url, text, title, cid, api_key, due_at, asset_type)
                print(f"  ✅ {service}: {post.get('id')} عند {post.get('dueAt', due_at)}")
                successes += 1
            except Exception as exc:
                failures.append((path.name, service, str(exc)))
                print(f"  ❌ {service}: {exc}")

    print(f"نجاح النشر: {successes}")
    for item in failures:
        print("فشل:", " | ".join(item))
    if successes == 0:
        raise RuntimeError("لم ينجح نشر أي أصل.")


def main() -> int:
    try:
        _run()
    except Exception as exc:
        print(f"⚠️ Buffer publishing skipped (non-fatal; remaining workflow continues): {exc}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
