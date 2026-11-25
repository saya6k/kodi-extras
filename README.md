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
