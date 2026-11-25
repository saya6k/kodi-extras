# kodi-extras

Kodi 애드온과, 애드온이 쓰는 OSMC(Vero V) 패키지를 모아 둔 저장소입니다.

## 애드온

| 애드온 | 하는 일 | 패키지 | 문서 |
|---|---|---|---|
| `script.service.threadbridge` | 802.15.4 USB 동글로 Thread 보더 라우터(OTBR)를 돌립니다. Home Assistant, Apple Home, Google Home과 함께 씁니다. | `threadbridge` | [docs/threadbridge.md](docs/threadbridge.md) |
| `service.atmos67` | Kodi가 패스스루한 Atmos·DTS를 스피커 배치에 맞게 디코딩해 AES67 스피커로 보냅니다. | `atmos67` | [docs/atmos67.md](docs/atmos67.md) |
| `plugin.video.chzzk` | 치지직의 라이브와 동영상을 봅니다. | 없음 | [docs/chzzk.md](docs/chzzk.md) |

threadbridge와 atmos67은 설정 화면 역할이고, 실제 일은 `.deb` 패키지의 systemd 서비스가 합니다. 애드온은 설정을 `~/.kodi/userdata/addon_data/<애드온 id>/`에 쓰고 `sudo -n systemctl`로 서비스를 다시 시작합니다. OSMC의 `osmc` 사용자는 암호 없이 sudo를 쓸 수 있습니다. 패키지는 Vero V의 OSMC(Debian bullseye armhf, Kodi 21)용입니다. threadbridge는 arm64 패키지도 있습니다. 치지직 플러그인은 Python만으로 돌아서 패키지가 필요 없고, Kodi가 도는 곳이면 어디서나 씁니다.

## 설치 (OSMC)

1. 쓸 애드온에 패키지가 있으면 [Releases](https://github.com/saya6k/kodi-extras/releases)에서 받아 Vero V에 설치합니다.

   ```sh
   sudo apt install ./threadbridge_<버전>_armhf.deb
   ```

2. Kodi에 저장소를 추가합니다. 설정 → 파일 관리자 → 소스 추가에서 `https://saya6k.github.io/kodi-extras/`를 추가합니다. 그다음 설정 → 애드온 → zip 파일에서 설치로, 그 소스의 `repository.kodiextras-<버전>.zip`을 설치합니다.
3. 저장소에서 설치 → kodi-extras에서 애드온을 설치합니다. 이후 업데이트는 Kodi가 저장소에서 받습니다.

## 구조

```
kodi-extras/
├── addons/                      # Kodi 애드온
│   ├── plugin.video.chzzk/
│   ├── script.service.threadbridge/
│   └── service.atmos67/
├── packages/                    # 애드온이 쓰는 OSMC 패키지(.deb)의 빌드
│   ├── threadbridge/            #   ot-br-posix를 받아 빌드
│   └── atmos67/                 #   ~/Projects/atmos67의 커밋을 받아 빌드
├── repository/                  # Kodi 저장소 애드온과 수록 목록(addons.txt)
├── scripts/                     # 애드온 zip, 저장소 빌드
├── tests/                       # 애드온·저장소 단위 시험, integration/은 통합 시험
└── docs/                        # 애드온별 문서
```

패키지가 빌드하는 소스는 이 저장소에 없습니다. threadbridge는 ot-br-posix의 릴리스 태그(`packages/threadbridge/otbr-options`)를, atmos67은 atmos67 저장소의 커밋(`packages/atmos67/atmos67-source`)을 빌드할 때 받아 옵니다. 빌드 산출물(`build/`, `out/`, `dist/`)은 git에 넣지 않습니다.

## 개발

```sh
python3 -m unittest discover -s tests              # 단위 시험 (Kodi 없이)
scripts/package-addon.sh script.service.threadbridge   # → dist/<id>-<버전>.zip
```

패키지 빌드와 통합 시험은 Docker에서 돌립니다. 명령은 각 애드온 문서에 있습니다.

## 배포

**Kodi 저장소**는 `main`에 push될 때마다 GitHub Actions(`.github/workflows/pages.yml`)가 빌드해 GitHub Pages(`https://saya6k.github.io/kodi-extras/`)에 올립니다. 애드온을 업데이트하려면 `addon.xml`의 버전을 올려 PR로 머지하면 됩니다. Kodi는 버전이 오른 애드온만 업데이트합니다.

같은 것을 로컬에서 만들려면 다음을 실행합니다.

```sh
scripts/build-repository.py https://<배포 주소>
```

`repository/addons.txt`에 적힌 애드온과 `repository.kodiextras`를 `dist/repo/`에 만듭니다. 이 폴더를 그대로 그 주소에 올리면 Kodi 저장소가 됩니다. 주소는 인증 없이 열려야 합니다. `index.html`에는 저장소 애드온 zip의 링크가 들어 있습니다. Kodi 파일 관리자가 그 주소를 폴더처럼 열 수 있게 하기 위해서입니다.

이미 설치된 Kodi는 저장소 애드온에 적힌 주소에서 업데이트를 찾습니다. 그래서 배포 주소를 바꿀 때는 `repository.kodiextras`의 버전을 올려 새 주소로 빌드하고, 그 결과를 예전 주소에도 올려 두어야 옮겨 갑니다.

**`.deb` 패키지**는 Kodi 저장소에 들어가지 않고 GitHub Releases에 올립니다. 패키지를 빌드한 뒤(각 문서의 "빌드") 다음을 실행합니다.

```sh
scripts/release-package.sh threadbridge   # → 릴리스 threadbridge-v<버전>에 out/의 .deb를 올림
```

버전은 그 패키지의 `build.sh`의 `version=`입니다. 릴리스가 없으면 만들고, 같은 이름의 파일은 바꿔 올립니다. atmos67은 로컬의 atmos67 저장소에서 빌드하므로 CI가 아니라 이 스크립트로 올립니다.
