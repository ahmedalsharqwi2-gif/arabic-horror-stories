# Arabic horror stories

## مراجعة الصورة والصوت

راجع [CLIP_REVIEW.md](CLIP_REVIEW.md) لإعداد مراجعة المقاطع الفعلية والصوت قبل النشر، وتشخيص توقف المسار عند عدم وجود مشهد مطابق.


### Bounded visual fallback
Pexels candidates are bounded before falling back to Wikimedia Commons public-domain / CC0 JPEG or PNG images. Images are fitted to the frame, animated with FFmpeg, and inspected by the existing actual-media gate before acceptance. Provider errors never grant approval. Source and license metadata are retained beside each animated clip. No API key is required for Commons. Pixabay and Mixkit are not yet integrated. This does not change the episode duration or publication schedule.
