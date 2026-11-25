# threadbridge

Kodi 박스에 802.15.4 USB 동글을 꽂아 Thread 보더 라우터(OTBR)로 쓰게 합니다. ot-br-posix의 `otbr-agent`를 systemd 서비스로 돌리고, Kodi 애드온에서 설정과 Thread 네트워크 관리를 합니다.

- `packages/threadbridge`: `.deb` 패키지. OSMC(Vero V)용 armhf와, Debian 계열 64비트 ARM 배포판(Raspberry Pi OS 64비트 등)용 arm64가 있습니다. `otbr-agent`, `ot-ctl`, 서비스와 방화벽 스크립트가 들어 있습니다.
- `addons/script.service.threadbridge`: Kodi 애드온. 동글·네트워크 설정, 상태 보기, 네트워크 만들기, dataset 가져오기·내보내기, joiner 추가를 합니다.

## 동글

동글에는 OpenThread **RCP** 펌웨어가 올라가 있어야 합니다. Zigbee 펌웨어나 멀티프로토콜(Zigbee+Thread) 펌웨어로는 안 됩니다.

| 동글 | 보드레이트 | 흐름 제어 |
|---|---|---|
| Home Assistant Connect ZBT-1 / SkyConnect | 460800 | 켬 |
| Sonoff ZBDongle-E (EFR32MG21) | 460800 | 켬 |
| nRF52840 Dongle, MDK 등 | 115200 | 끔 |

보드레이트와 흐름 제어는 펌웨어마다 다를 수 있으니 펌웨어 설명을 따릅니다. 장치는 `/dev/serial/by-id`의 이름으로 고릅니다. 이 이름은 다시 꽂아도 바뀌지 않습니다. 설정을 비워 두면 처음 찾은 동글을 씁니다.

## 빌드

```sh
docker build -t threadbridge-build packages/threadbridge
docker run --rm -v "$PWD":/work -w /work threadbridge-build packages/threadbridge/build.sh armhf
docker run --rm -v "$PWD":/work -w /work threadbridge-build packages/threadbridge/build.sh arm64
# → packages/threadbridge/out/threadbridge_<version>_armhf.deb, threadbridge_<version>_arm64.deb
```

빌드 머신과 아키텍처가 같으면 네이티브로, 다르면 크로스 컴파일러로 빌드합니다. 아키텍처를 빼면 armhf입니다. 둘 다 bullseye에서 빌드하므로 glibc 2.31 이상이면 돕니다. Debian 11~13과 그 위의 배포판이 해당합니다.

ot-br-posix 버전과 빌드 옵션은 `packages/threadbridge/otbr-options`에 있습니다. 패키지에 들어가는 구성 요소의 라이선스 고지(`/usr/share/doc/threadbridge/copyright`)는 빌드할 때 `copyright.sh`가 소스의 라이선스 파일로 만듭니다. 빌드 이미지는 bullseye의 snapshot.debian.org 저장소를 씁니다. bullseye 미러가 아카이브로 옮겨 가는 중이어서 일반 미러로는 설치가 실패하기 때문입니다.

## 시험

```sh
python3 -m unittest discover -s tests          # 애드온의 Kodi 없는 로직

docker build -t threadbridge-test tests/integration/threadbridge
docker run --rm --privileged --sysctl net.ipv6.conf.all.disable_ipv6=0 -v "$PWD":/work threadbridge-test sh /work/tests/integration/threadbridge/run.sh
```

통합 시험은 `otbr-agent`를 네이티브로 빌드합니다. OpenThread의 시뮬레이션 RCP를 socat pty 뒤에 두고 `/dev/serial/by-id`에 연결해 동글 대신 씁니다. 그 위에서 패키지의 `threadbridge-run`을 그대로 실행하고, 애드온의 REST 클라이언트로 네트워크 만들기, dataset 내보내기·가져오기, 커미셔너·joiner 추가를 시험합니다. 마지막으로 방화벽 규칙이 생기고 지워지는지 확인합니다.

## 설치 (OSMC)

```sh
sudo apt install ./threadbridge_<version>_armhf.deb
```

OSMC가 아닌 arm64 배포판에서는 `_arm64.deb`를 설치합니다. 그다음 Kodi에서 애드온을 설치합니다. kodi-extras 저장소에서 설치하거나(README의 "설치"), `scripts/package-addon.sh script.service.threadbridge`로 만든 zip을 zip 파일로 설치합니다. 애드온 설정을 바꾸면 그 내용이 `~/.kodi/userdata/addon_data/script.service.threadbridge/threadbridge.conf`에 쓰이고 서비스가 재시작됩니다. 재시작에는 `sudo -n systemctl`을 쓰는데, OSMC의 `osmc` 사용자는 암호 없이 sudo를 쓸 수 있습니다. 패키지 기본값은 `/etc/threadbridge/threadbridge.conf`에 있습니다.

서비스가 켜질 때 하는 일입니다.

- IPv6 포워딩을 켭니다. 포워딩을 켜면 Linux가 RA를 무시하기 때문에, 백본 인터페이스의 `accept_ra`를 2로, `accept_ra_rt_info_max_plen`을 64로 둡니다.
- 유입 필터를 겁니다. ipset과 `OTBR_FORWARD_INGRESS` ip6tables 체인으로, ot-br-posix의 `otbr-firewall`과 같습니다.
- NAT64를 켜 두었다면 IPv4 포워딩과 NAT44 MASQUERADE도 겁니다.
- 서비스가 멈추면 위 규칙을 지웁니다.

### OSMC가 아닌 배포판

서비스는 그대로 돌지만, 애드온과 이어 주는 부분은 OSMC를 전제로 합니다. 서비스는 애드온 설정을 `/home/osmc/.kodi/...`에서 읽고, 애드온은 서비스를 재시작할 때 암호 없는 `sudo`를 씁니다. Kodi를 다른 사용자(예: `kodi`)로 돌린다면 두 가지를 맞춥니다.

```sh
# 애드온 설정을 읽을 위치를 그 사용자의 것으로 (패키지를 업그레이드해도 남습니다)
sudo systemctl edit threadbridge
#   [Service]
#   EnvironmentFile=-/home/kodi/.kodi/userdata/addon_data/script.service.threadbridge/threadbridge.conf

# 그 사용자가 암호 없이 서비스를 재시작할 수 있게
echo 'kodi ALL=(root) NOPASSWD: /bin/systemctl restart threadbridge.service, /usr/bin/systemctl restart threadbridge.service' \
    | sudo tee /etc/sudoers.d/threadbridge
```

애드온 없이 쓴다면 `/etc/threadbridge/threadbridge.conf`를 고치고 `sudo systemctl restart threadbridge`를 하면 됩니다.

## 함께 쓰기

- **Home Assistant**: Open Thread Border Router 통합에 `http://<박스 주소>:8081`을 넣습니다. HA가 다른 기기에서 돈다면 애드온의 "REST API를 네트워크에 공개"를 켜야 합니다. **REST API에는 인증이 없습니다.** 공개하면 같은 네트워크의 누구나 Thread 네트워크를 바꿀 수 있습니다.
- **Apple Home / Google Home**: 이미 있는 Thread 네트워크에 합류하려면 그 네트워크의 dataset이 필요합니다. 보통 Home Assistant의 Thread 통합에서 가져옵니다. 애드온의 "dataset으로 합류"에 넣습니다.
- **단독**: 애드온의 "새 네트워크 만들기"로 만듭니다. 다른 컨트롤러에 넘길 때는 "dataset 내보내기"를 씁니다. 내보낸 dataset은 화면에 보이고, 애드온 데이터 폴더의 `dataset.txt`에도 저장됩니다.

Matter 기기는 Thread joiner가 아니라 Matter 컨트롤러(HA, Apple Home, Google Home)로 추가합니다. 애드온의 "기기 추가 (joiner)"는 PSKd로 합류하는 Thread 1.x 방식의 기기용입니다.

## 확인하지 않은 것

모두 실기(Vero V, arm64 장비)와 실제 동글에서 아직 확인하지 않았습니다. arm64 패키지는 통합 시험과 같은 빌드 옵션입니다. 통합 시험을 arm64 Linux에서 돌리면, 시험하는 `otbr-agent`가 arm64 네이티브 빌드입니다.

- **커널 기능**: Vero V 커널에 TUN, ip6tables, ipset(`ip_set_hash_net`, `xt_set`), `accept_ra_rt_info_max_plen`이 있는지 모릅니다. ipset이 없으면 서비스가 시작되지 않습니다. 그때는 유입 필터를 끄면 되지만 보안이 약해집니다.
- **USB 시리얼 드라이버**: ZBT-1·SkyConnect는 CP210x, ZBDongle-E는 CH9102 칩을 씁니다. OSMC 커널에 해당 드라이버가 있는지 모릅니다.
- **avahi와의 공존**: OSMC의 avahi-daemon과 OpenThread mDNS가 5353 포트를 함께 쓰는 것은 소스(`SO_REUSEPORT`)로만 확인했습니다.
- **connman**: OSMC의 connman이 sysctl(`accept_ra`, forwarding)을 되돌리는지 모릅니다.
