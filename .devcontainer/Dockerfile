# Azure Cognitive Services requires Debian 9/10/11
FROM python:3.11.4-slim-bullseye

# Azure Cognitive Services requires build-essential libssl-dev ca-certificates libasound2 wget
# Gradio mp3 to wav requires ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends wget curl nano lsb-release ffmpeg build-essential libssl-dev ca-certificates libasound2

# Install ZSH
RUN apt-get update && sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v1.1.5/zsh-in-docker.sh)" -- \
    -t simple \
    -p git -p ssh-agent -p 'history-substring-search'

RUN apt-get autoremove -y

# Install Python libraries
RUN pip3 install --upgrade pip
COPY requirements.txt .
RUN pip3 install -r requirements.txt

WORKDIR /work

ENTRYPOINT ["/bin/bash"]