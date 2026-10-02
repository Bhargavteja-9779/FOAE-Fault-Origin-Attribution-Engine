#!/usr/bin/env bash
# Download the five public datasets used in the paper into data/raw (~5 GB before cleanup).
set -euo pipefail
ROOT="${OCWD_DATA:-$(cd "$(dirname "$0")/.." && pwd)/data/raw}"
mkdir -p "$ROOT" && cd "$ROOT"
git clone --depth 1 https://github.com/gsoh/VED VED
( cd VED/Data && for f in VED_DynamicData_Part*.7z; do 7z x -y "$f" -o../dyn >/dev/null; done )
git clone --depth 1 https://github.com/Asr-roque/canmodes-datasets canmodes-datasets
git clone --depth 1 https://github.com/sampathrajapaksha/CAN-MIRGU CAN-MIRGU
git clone --depth 1 https://github.com/JehadAlyateem/Car-Hacking-Dataset CHD
( cd CHD && mkdir -p x && for z in *.zip; do unzip -o -q "$z" -d x; done )
git clone --depth 1 https://bitbucket.org/brooke-lampe/can-dataset can-dataset
# keep only what is used (the attack-free drives) to save disk space
find can-dataset -mindepth 2 -maxdepth 2 -type d ! -name attack-free -exec rm -rf {} +
echo "Datasets ready in $ROOT"
