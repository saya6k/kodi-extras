# atmos67

Kodi가 재생하는 영상의 오디오를 Vero V에서 디코딩해 AES67 스피커로 보냅니다. Dante 스피커·앰프를 AES67 모드로 쓰는 경우가 대표적입니다. Kodi는 비트스트림을 ALSA 루프백으로 패스스루하고, atmos67이 그것을 캡처합니다. atmos67은 디코딩하고, 스피커 배치에 맞게 렌더하고, 보정하고, RTP·SAP·PTP로 직접 송출합니다.

```
Kodi ─> ALSA 루프백 ─> atmos67 ─> atmos67 --aes67-send ─> AES67 (RTP)
(패스스루) (snd-aloop)  (디코딩)    (보정·송출)              ptp4l (PTP)
```

- `packages/atmos67`: OSMC(Vero V, Debian bullseye armhf)용 `.deb`. `atmos67` 바이너리와 서비스 세 개(`atmos67`, `atmos67-ptp4l`, `atmos67-phc2sys`), ALSA 루프백 설정이 들어 있습니다.
- `addons/service.atmos67`: Kodi 애드온. 스피커 배치, 네트워크, 스트림 구성, 베이스 매니지먼트·레벨, 룸 보정 마법사, 영상 동기, Dante 수신기 연결을 맡습니다. Kodi의 볼륨도 송출기로 넘깁니다.

atmos67 자체는 atmos67 저장소(`~/Projects/atmos67`, 원격 없음)에서 개발합니다. 지원하는 포맷, 보정, 성능, 확인한 것과 확인하지 못한 것은 그 저장소의 README가 기준입니다. 특히 "OSMC (Vero V) 패키지" 절을 봅니다. 이 문서는 kodi-extras에서 빌드하고 설치하는 방법만 다룹니다.

## 빌드

패키지는 atmos67 저장소의 커밋 하나를 꺼내 빌드합니다. 그 커밋은 `packages/atmos67/atmos67-source`의 `ATMOS67_REV`입니다. 저장소를 읽기 전용으로 마운트하고 `git archive`로 꺼내므로, 커밋하지 않은 변경은 패키지에 들어가지 않습니다. atmos67 저장소에서 고친 것을 넣으려면 그쪽에서 커밋한 뒤 `ATMOS67_REV`를 바꿉니다.

```sh
docker build -t atmos67-armhf packages/atmos67
docker run --rm -v "$PWD":/work -v ~/Projects/atmos67:/atmos67:ro -w /work atmos67-armhf packages/atmos67/build.sh
# → packages/atmos67/out/atmos67_<버전>_armhf.deb, service.atmos67-<버전>.zip
```

빌드 중에 atmos67의 시험을 armhf 바이너리로 돌립니다. 그래서 커널에 32비트 ARM용 qemu가 등록돼 있어야 합니다. Docker Desktop은 이미 돼 있고, 다른 곳에서는 `docker run --privileged --rm tonistiigi/binfmt --install arm`으로 등록합니다.

시험용 64비트 정적 바이너리도 만들 수 있습니다. arm64 Linux에서 합니다.

```sh
docker build -t atmos67-aarch64 -f packages/atmos67/Dockerfile.aarch64 packages/atmos67
docker run --rm -v "$PWD":/work -v ~/Projects/atmos67:/atmos67:ro -w /work atmos67-aarch64 packages/atmos67/build-aarch64.sh
# → packages/atmos67/out/atmos67-<버전>-aarch64
```

Vero V는 userland가 32비트지만 커널은 arm64라서, 이 바이너리를 패키지의 `/usr/bin/atmos67` 대신 쓸 수 있을 것으로 봅니다. 실기에서는 확인하지 않았습니다. 바꿔 쓰는 방법과 비교 방법은 atmos67 저장소 README의 "64비트 바이너리 (시험용)"에 있습니다.

## 시험

```sh
python3 -m unittest tests/test_atmos67.py
```

애드온 가운데 Kodi에 의존하지 않는 로직을 시험합니다. 대상은 다음과 같습니다.

- 설정으로 서비스 설정 파일을 만드는 부분(보정 모드별 크로스오버·레벨·지연)
- Kodi 볼륨을 dB로 바꾸는 부분
- 영상 동기 오프셋 계산
- 송출기 제어 소켓과의 통신
- 스트림 구성
- 레벨 저장

## 설치 (OSMC)

```sh
sudo apt install ./atmos67_<버전>_armhf.deb   # alsa-utils, linuxptp, ethtool을 함께 설치합니다.
```

패키지는 `snd-aloop` 모듈을 올리고 서비스 세 개를 켭니다. 그다음 Kodi에서 다음 순서로 진행합니다.

1. 애드온을 설치합니다. kodi-extras 저장소에서 설치하거나, `service.atmos67-<버전>.zip`을 zip 파일로 설치합니다.
2. 애드온 설정에서 스피커 배치, 네트워크 인터페이스, 멀티캐스트 주소, PTP 도메인을 고릅니다. 바꾸면 서비스가 다시 시작됩니다.
3. 애드온 설정의 "Kodi 오디오 출력을 atmos67로 설정"을 실행합니다. 오디오 출력과 패스스루 장치가 `atmos67 (AES67)`로 바뀌고 패스스루가 켜집니다. 장치가 목록에 보이려면 Kodi를 다시 시작해야 할 수 있습니다.

애드온의 설정은 `~/.kodi/userdata/addon_data/service.atmos67/atmos67.conf`에 쓰입니다. 패키지 기본값은 `/etc/atmos67/atmos67.conf`에 있습니다. 애드온 없이 쓰려면 이 파일을 고치고 `sudo systemctl restart atmos67`을 합니다.

## 라이선스

atmos67은 GPL-3.0-only입니다. 패키지의 바이너리에는 FFmpeg(LGPL)와 SECS 2R(AGPL-3.0-only)이 정적으로 들어 있습니다. 그래서 `.deb`를 배포할 때는 두 라이선스의 조건도 따라야 합니다. 자세한 내용은 atmos67 저장소 README의 "알아 둘 것"에 있습니다.
