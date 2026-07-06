# Memex remote-control — TWA (Trusted Web Activity) APK build environment.
# Wraps the existing PWA (memex.shivelymedia.com) in a sideloadable Android APK.
#
# Self-contained: Node + JDK 17 + Android SDK + Bubblewrap. No host toolchain.
FROM node:20-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-17-jdk-headless unzip wget python3 \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk

# Android command-line tools + the platform/build-tools Bubblewrap needs.
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && cd /tmp \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O cmdtools.zip \
    && unzip -q cmdtools.zip -d ${ANDROID_HOME}/cmdline-tools \
    && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && rm cmdtools.zip
ENV PATH="${PATH}:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools"
RUN yes | sdkmanager --licenses >/dev/null 2>&1 \
    && sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0" >/dev/null

# Bubblewrap CLI (TWA generator/builder)
RUN npm install -g @bubblewrap/cli@1.24.1

# Point Bubblewrap at the in-image JDK + SDK so builds are non-interactive.
RUN mkdir -p /root/.bubblewrap \
    && printf '{"jdkPath":"%s","androidSdkPath":"%s"}' "${JAVA_HOME}" "${ANDROID_HOME}" \
       > /root/.bubblewrap/config.json

# Bubblewrap validates ${sdk}/tools (or /bin) and runs tools/bin/sdkmanager, but
# modern cmdline-tools live under cmdline-tools/latest — bridge it with a symlink.
RUN ln -s "${ANDROID_HOME}/cmdline-tools/latest" "${ANDROID_HOME}/tools"

WORKDIR /twa
COPY . /twa/
RUN chmod +x /twa/build.sh

ENTRYPOINT ["/twa/build.sh"]
