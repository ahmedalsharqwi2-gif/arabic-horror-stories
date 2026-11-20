# Preserved materials

All listed bytes preserved at their original paths, except the Nafhamha identity receives a new rebuild_tokens member and its exact original is saved beside it as nafhamha-identity.original.json. The full original source remains on the verified backup branch and tag. Additional extracted topic identifiers are in state/legacy-topic-index.json; new reservations never overwrite that index.

| Original path | SHA256 before rebuild |
|---|---|
| `config/channel_identity.json` | `5e5d8b43c44bef052848879074d8cc45127bbd647d029a528284df130cd32de9` |
| `config/arabic_pronunciation.json` | `942e37bd8c59e2295229348b01b403c09e2820f1593d4ee540b20bfdade205a2` |
| `state/topic_history.json` | `d4406ddb3e1a596f9fee4be4691877adb769a9aa5c33d33f66798bc2781a2c81` |
| `professional_motion/branding.json` | `484e938008c17d62fc53892b588af33aac9cd010b1463f213c9bf06c5e48690d` |
| `config/reviewed_episodes/nyos.json` | `1bbd90778fec8fac58660c52b9a15478d29f8bb060519fd7d77bd0543434af3e` |
| `photo_motion/assets/Noto-Fonts-Copyright.txt` | `075f91382875da1c4b491f1facf2586f55448705133264d98ce15cab6211b125` |
| `photo_motion/assets/NotoSansArabic-Bold.ttf` | `ded6fc7359ca36d15d7aab9ef0c066e21ce48b26a069994d6602fa2cb9a1b952` |
| `photo_motion/assets/NotoSansArabic-Regular.ttf` | `504d7407d86875acf7d04dfaa0fd7524d0b8797723bc4aa18022f29db25b0b6e` |
| `professional_motion/fonts/OFL-IBM-Plex.txt` | `7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da` |
| `professional_motion/fonts/Noto-Fonts-Copyright.txt` | `075f91382875da1c4b491f1facf2586f55448705133264d98ce15cab6211b125` |
| `professional_motion/fonts/NotoSansArabic-Bold.ttf` | `ded6fc7359ca36d15d7aab9ef0c066e21ce48b26a069994d6602fa2cb9a1b952` |
| `professional_motion/fonts/IBMPlexMono-Medium.ttf` | `a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755` |

Original logo present in checkout: no. The owner subsequently supplied inline logo references. Their original file bytes have not been exposed by the upload tool; no replacement has been drawn. See config/logo-intake.json. Original font files and their available notices remain. Charon and intended 17:00 Africa/Cairo destination names remain in config. No .mp4 files were tracked on the cloned main snapshots; no approved media was deleted from remote media branches. Legacy scheduling files are in the backup, but the new branch has only one active workflow.

## Follow-up original logo installation

Source: Owner supplied logos.zip / arabic-horror-stories.jpg

Canonical file: `brand/logo/logo.jpg`

SHA-256: `f4dd2c963a4541493ea44af45ee5398cdb063fc874a1e40a0fe7a4a276c2320a`

Byte-for-byte copy verified; no redraw, recolor, background removal, raster edit or vectorization. The public/brand/logo directory is a symlink to the canonical directory. Header, intro/outro and thumbnail use the same Logo component and source.
