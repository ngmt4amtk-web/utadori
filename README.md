# うたどり

歌入りの音源から旋律の下書きを作り、スマホで直して譜面にするWebアプリです。

- `docs/`: GitHub Pagesで配信する画面
- `server/`: 音高の検出と譜面の書き出しを行うサーバー

自動の結果は下書きです。音高の検出にはRMVPEを使います。モデルは `lj1995/VoiceConversionWebUI` の `rmvpe.onnx` を `server/models/` に置いてください。

音源は、利用者が権利を確かめて自分で選んだファイルを使ってください。
