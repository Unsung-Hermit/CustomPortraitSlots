# サードパーティ通知

このフォルダに含まれる、または元にしたサードパーティ製のコードとバイナリの出典です。

## repak（`Tools/repak.exe`）

- 同梱バイナリ。ライセンスは次のファイルのとおり、MIT または Apache-2.0 のデュアルライセンスです。
  - `repak_LICENSE-MIT.txt`
  - `repak_LICENSE-APACHE.txt`
- 著作権表示（MIT ファイルより）: Copyright 2024 Truman Kilen, spuds

## UAssetAPI（アルゴリズムの出典、`registry_writer.py`）

- `registry_writer.py` の名前ハッシュ算出（`generate_hash`、`_strihash`、`_strcrc32`）は、UAssetAPI の `CRCGenerator`（`CRCGenerator.cs`）と同じ式を、Python に書き直したものです。C# のコードは一行も含めていません。
- 上流: https://github.com/atenfyr/UAssetAPI
- 著作権表示（アセンブリ属性より）: Copyright © Atenfyr 2021
- ライセンス: MIT（下記）

### MIT License（UAssetAPI）

Copyright © Atenfyr 2021

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
