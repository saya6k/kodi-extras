# kodi-extras

Kodi 애드온 및 관련 패키지 모노레포.

## 구조

```
kodi-extras/
├── addons/                      # Kodi 애드온
│   ├── script.service.threadbridge/   # OTBR(OpenThread Border Router) 서비스
│   └── service.atmos67/               # atmos67(~/Projects/aes67) 서비스
├── packages/                    # 애드온에서 사용하는 패키지
│   ├── threadbridge/
│   └── atmos67/
├── repository/                  # Kodi 저장소 애드온
│   └── repository.kodiextras/
├── scripts/                     # 빌드/배포 스크립트
├── tests/                       # 애드온 로직 단위 시험, integration/ 은 통합 시험
├── docs/                        # 문서
└── README.md
```

- threadbridge: [docs/threadbridge.md](docs/threadbridge.md)

애드온 zip은 `scripts/package-addon.sh <애드온 id>`로 `dist/`에 만듭니다. 단위 시험은 `python3 -m unittest discover -s tests`로 돌립니다.

## Kodi 저장소

```sh
scripts/build-repository.py https://<배포 주소>
```

`repository/addons.txt`에 적힌 애드온과 `repository.kodiextras`를 `dist/repo/`에 만듭니다. 이 폴더를 그대로 그 주소에 올리면 Kodi 저장소가 됩니다. 주소는 인증 없이 열려야 합니다. 처음 설치할 때는 `dist/repo/repository.kodiextras-<버전>.zip`을 Kodi의 "zip 파일로 설치"로 넣습니다. 그다음부터는 애드온 버전을 올리고 다시 빌드해 올리면 Kodi가 업데이트를 받습니다.

이미 설치된 Kodi는 저장소 애드온에 적힌 주소에서 업데이트를 찾습니다. 그래서 배포 주소를 바꿀 때는 `repository.kodiextras`의 버전을 올려 새 주소로 빌드하고, 그 결과를 예전 주소에도 올려 두어야 옮겨 갑니다.
