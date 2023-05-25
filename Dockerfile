FROM continuumio/miniconda3

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
ENTRYPOINT ["/bin/bash", "--login", "-c", "while true; do python3 -Werror ./stam.py; done;"]
#ENTRYPOINT ["/bin/bash", "--login", "-c", "python3 ./stam.py"]
#ENTRYPOINT ["/bin/bash", "--login", "-c", "python3 -m pytest"]
