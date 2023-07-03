FROM continuumio/miniconda3:master-alpine


RUN apk update
RUN apk upgrade
RUN apk add bash git
RUN apk add gcc # TODO: only run when not on x64

RUN mkdir /stampydata
WORKDIR /stampy

RUN --mount=type=cache,mode=0755,target=/root/.cache/pip conda update --all
# Create the environment:
COPY environment.yml .
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip conda env create -f environment.yml

# Make RUN commands use the new environment:
RUN echo "conda activate stampy" >> ~/.profile
SHELL ["/bin/bash", "--login", "-c"]
RUN --mount=type=cache,mode=0755,target=/root/.cache/pip conda activate stampy && conda install pytest
RUN conda clean -a

COPY . .
ENV STAMPY_RUN_TESTS=${STAMPY_RUN_TESTS}
ENTRYPOINT ["/bin/bash", "--login", "./runstampy"]
