#!/bin/sh
set -eu
SOURCE_COMMIT=9b488bc7a1e9b61713082f3e6c4361988d62f77b
SOURCE_SHA256=01eb0496c85b79c7a1c018241b09b63893259975672a2a12b9c44cf33ab26cb7
printf '%s  /input/source.tar.gz\n' "$SOURCE_SHA256" | sha256sum -c -
cat /etc/os-release
gcc --version
aarch64-linux-gnu-gcc --version
make --version
dpkg-query -W
mkdir -p /build/source /build/obj
tar --no-same-owner -xzf /input/source.tar.gz -C /build/source
cd "/build/source/linux-$SOURCE_COMMIT"
make O=/build/obj ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- bcm2711_defconfig
make -j2 O=/build/obj ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- V=1 broadcom/bcm2710-rpi-zero-2-w.dtb
cp /build/obj/.config /output/kernel.config
cp /build/obj/arch/arm64/boot/dts/broadcom/bcm2710-rpi-zero-2-w.dtb /output/rebuilt.dtb
cp /build/obj/arch/arm64/boot/dts/broadcom/.bcm2710-rpi-zero-2-w.dtb.cmd /output/dtb-command.txt
/build/obj/scripts/dtc/dtc --version
sha256sum /output/kernel.config /output/rebuilt.dtb /output/dtb-command.txt
