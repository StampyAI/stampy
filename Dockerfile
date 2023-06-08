FROM continuumio/miniconda3

# TODO: only run when not on x64
RUN apt-get update
RUN apt-get install gcc -y

RUN mkdir /stampydata
WORKDIR /stampy

# Create the environment:
COPY environment.yml .
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip conda env create -f environment.yml

# Make RUN commands use the new environment:
RUN echo "conda activate stampy" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip conda activate stampy && conda install pytest

COPY . .
ENV STAMPY_RUN_TESTS=${STAMPY_RUN_TESTS}
ENTRYPOINT ["/bin/bash", "--login", "./runstampy"]
