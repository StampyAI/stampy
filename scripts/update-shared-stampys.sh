#!/bin/bash

# This script is for use on the Stampy server managing multiple docker instances.

set -eu

PROJECT_DIR=$HOME
host_list=$(cat ~/served_hosts)

sanity_check() {
    local target="${PROJECT_DIR}/$1"
    local task="check dir '${target}'exists"
    cd "${target}" && echo "$task: $1"
    if [ ! -d "${target}/.git" ]; then
        echo "Dir ${target}/.git does not exist"
        exit 1
    fi
}
git_update () {
    local task="update and prune git repo"
    cd "${PROJECT_DIR}/$1" && echo "$task: $1"
    git pull --rebase=true --depth=1 -q
    git gc --prune=now -q
}
image_build () {
    local task="build image"
    cd "${PROJECT_DIR}/$1" && echo "$task: $1"
    podman-compose --podman-args '--format=docker --pull=newer -q' build
}
actually_update () {
    local task="restart service"
    cd "${PROJECT_DIR}/$1" && echo "$task: $1"
    podman-compose down
    podman-compose up -d
}
post_cleanup () {
    echo "prune intermediate images"
    podman system prune -af
}

sanity_check "stampy"
for host in $host_list; do
    sanity_check $host
done

# Main stampy folder should have been updated by external action,
# as to update this script.
for host in $host_list; do
    git_update $host
done

for host in $host_list; do
    image_build $host
done

for host in $host_list; do
    actually_update $host
done

post_cleanup

echo "Update script successful!"

exit 0
